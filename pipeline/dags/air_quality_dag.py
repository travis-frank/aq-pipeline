"""Airflow DAG: ingest OpenAQ data, load raw JSON to Postgres, run dbt."""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

# In Docker: AIRFLOW_REPO_ROOT=/opt/aq-pipeline (set in docker-compose).
# On host (local DAG parse): fall back to repo root from this file's location.
REPO_ROOT = Path(
    os.environ.get("AIRFLOW_REPO_ROOT", Path(__file__).resolve().parents[2])
)
INGESTION_DIR = REPO_ROOT / "ingestion"
PIPELINE_DIR = REPO_ROOT / "pipeline"
DBT_DIR = PIPELINE_DIR / "dbt"

for path in (str(REPO_ROOT), str(INGESTION_DIR), str(PIPELINE_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

# dbt 1.12+ expects project-dir via cwd, not as a global CLI flag.
DBT_RUN_CMD = f"cd {DBT_DIR} && dbt run"
DBT_TEST_CMD = f"cd {DBT_DIR} && dbt test"


def _run_ingestion() -> None:
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


def _load_raw_to_postgres() -> None:
    from load_raw import DEFAULT_RAW_DIR, load_dotenv, load_raw

    load_dotenv()
    loaded = load_raw(raw_dir=DEFAULT_RAW_DIR)
    logger.info("Loaded %s raw file(s) into raw.openaq_pulls", loaded)


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

    ingest >> load_raw >> dbt_run >> dbt_test
