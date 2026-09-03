"""Airflow DAG: ingest OpenAQ data, load raw JSON to Postgres, run dbt."""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.utils.state import State

logger = logging.getLogger(__name__)

# In Docker: AIRFLOW_REPO_ROOT=/opt/aq-pipeline (set in docker-compose).
# On host (local DAG parse): fall back to repo root from this file's location.
REPO_ROOT = Path(
    os.environ.get("AIRFLOW_REPO_ROOT", Path(__file__).resolve().parents[2])
)
INGESTION_DIR = REPO_ROOT / "ingestion"
PIPELINE_DIR = REPO_ROOT / "pipeline"
DBT_DIR = PIPELINE_DIR / "dbt"
DBT_RUN_RESULTS = DBT_DIR / "target" / "run_results.json"
DBT_RUN_RESULTS_SNAPSHOT = DBT_DIR / "target" / "run_results_run.json"

PIPELINE_TASK_IDS = (
    "run_ingestion",
    "load_raw_to_postgres",
    "dbt_run",
    "dbt_test",
)

for path in (str(REPO_ROOT), str(INGESTION_DIR), str(PIPELINE_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

# dbt 1.12+ expects project-dir via cwd, not as a global CLI flag.
# Snapshot run_results.json before dbt test overwrites it.
DBT_RUN_CMD = (
    f"cd {DBT_DIR} && dbt run "
    f"&& cp target/run_results.json target/run_results_run.json"
)
DBT_TEST_CMD = f"cd {DBT_DIR} && dbt test"


def _run_ingestion() -> dict:
    from openaq_client import DEFAULT_CONFIG_PATH, DEFAULT_OUTPUT_DIR, run_ingestion

    summary = run_ingestion(
        config_path=DEFAULT_CONFIG_PATH,
        output_dir=DEFAULT_OUTPUT_DIR,
    )
    logger.info(
        "Ingestion complete: %s/%s locations pulled",
        summary.locations_pulled,
        summary.locations_attempted,
    )
    if summary.errors:
        logger.warning("Ingestion errors: %s", summary.errors)

    return asdict(summary)


def _load_raw_to_postgres() -> dict:
    from load_raw import DEFAULT_RAW_DIR, load_dotenv, load_raw

    load_dotenv()
    loaded = load_raw(raw_dir=DEFAULT_RAW_DIR)
    logger.info("Loaded %s raw file(s) into raw.openaq_pulls", loaded)
    return {"rows_loaded": loaded}


def _log_pipeline_run(**context) -> None:
    from log_pipeline_run import (
        parse_dbt_run_results,
        parse_dbt_test_results,
        rows_ingested_from_summary,
        write_pipeline_run,
    )

    ti = context["ti"]
    dag_run = context["dag_run"]

    ingestion_summary = ti.xcom_pull(task_ids="run_ingestion")
    load_summary = ti.xcom_pull(task_ids="load_raw_to_postgres")

    rows_ingested = (
        rows_ingested_from_summary(ingestion_summary)
        if ingestion_summary
        else None
    )
    rows_transformed = parse_dbt_run_results(DBT_RUN_RESULTS_SNAPSHOT)
    dbt_tests_run, dbt_tests_passed = parse_dbt_test_results(DBT_RUN_RESULTS)

    failures: list[str] = []
    for task_id in PIPELINE_TASK_IDS:
        task_instance = dag_run.get_task_instance(task_id)
        if task_instance is None:
            continue
        if task_instance.state in State.failed_states:
            failures.append(f"{task_id} ({task_instance.state})")

    if ingestion_summary and ingestion_summary.get("errors"):
        for error in ingestion_summary["errors"]:
            failures.append(f"run_ingestion: {error}")

    status = "failed" if failures else "success"
    error_message = "; ".join(failures) if failures else None

    start = dag_run.start_date
    if start and start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    end = datetime.now(timezone.utc)
    duration_seconds = (end - start).total_seconds() if start else None
    dag_run_ts = start or end

    run_id = write_pipeline_run(
        dag_run_ts=dag_run_ts,
        rows_ingested=rows_ingested,
        rows_transformed=rows_transformed,
        dbt_tests_run=dbt_tests_run,
        dbt_tests_passed=dbt_tests_passed,
        duration_seconds=duration_seconds,
        status=status,
        error_message=error_message,
    )
    logger.info(
        "pipeline_runs %s: ingested=%s transformed=%s tests=%s/%s status=%s",
        run_id,
        rows_ingested,
        rows_transformed,
        dbt_tests_passed,
        dbt_tests_run,
        status,
    )


with DAG(
    dag_id="air_quality",
    description="OpenAQ ingest -> raw load -> dbt run -> dbt test",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["openaq", "ingestion", "dbt"],
) as dag:
    ingest = PythonOperator(
        task_id="run_ingestion",
        python_callable=_run_ingestion,
    )

    load_raw = PythonOperator(
        task_id="load_raw_to_postgres",
        python_callable=_load_raw_to_postgres,
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=DBT_RUN_CMD,
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=DBT_TEST_CMD,
    )

    log_pipeline_run = PythonOperator(
        task_id="log_pipeline_run",
        python_callable=_log_pipeline_run,
        trigger_rule="all_done",
    )

    ingest >> load_raw >> dbt_run >> dbt_test >> log_pipeline_run
