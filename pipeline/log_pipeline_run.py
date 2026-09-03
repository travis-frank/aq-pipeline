"""Write pipeline run metrics to the pipeline_runs table."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2

logger = logging.getLogger(__name__)

INSERT_SQL = """
INSERT INTO pipeline_runs (
    dag_run_ts,
    rows_ingested,
    rows_transformed,
    dbt_tests_run,
    dbt_tests_passed,
    duration_seconds,
    status,
    error_message
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
RETURNING run_id;
"""


def rows_ingested_from_summary(summary: dict[str, Any]) -> int | None:
    """Sum measurement counts from a serialized PullSummary dict."""
    total = 0
    for location in summary.get("locations", []):
        for sensor in location.get("sensors", []):
            total += int(sensor.get("measurement_count", 0))
    return total


def parse_dbt_run_results(path: Path) -> int | None:
    """Sum rows_affected from dbt run's run_results.json snapshot."""
    if not path.is_file():
        return None

    data = json.loads(path.read_text(encoding="utf-8"))
    total = 0
    found = False
    for result in data.get("results", []):
        if result.get("status") != "success":
            continue
        adapter = result.get("adapter_response") or {}
        rows = adapter.get("rows_affected")
        if rows is not None:
            total += int(rows)
            found = True
    return total if found else None


def parse_dbt_test_results(path: Path) -> tuple[int | None, int | None]: 
    """Read dbt test counts from run_results.json after dbt test."""
    if not path.is_file():
        return None, None

    data = json.loads(path.read_text(encoding="utf-8"))
    results = data.get("results", [])
    tests_run = len(results)
    tests_passed = sum(1 for result in results if result.get("status") == "pass")
    return tests_run, tests_passed


def db_connect():
    """Connect to the warehouse Postgres using DB_* env vars."""
    required = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing database env vars: {', '.join(missing)}")

    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )


def write_pipeline_run(
    *,
    dag_run_ts: datetime,
    rows_ingested: int | None,
    rows_transformed: int | None,
    dbt_tests_run: int | None,
    dbt_tests_passed: int | None,
    duration_seconds: float | None,
    status: str,
    error_message: str | None,
) -> str:
    """Insert one pipeline_runs row and return run_id as a string."""
    conn = db_connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    INSERT_SQL,
                    (
                        dag_run_ts,
                        rows_ingested,
                        rows_transformed,
                        dbt_tests_run,
                        dbt_tests_passed,
                        duration_seconds,
                        status,
                        error_message,
                    ),
                )
                run_id = cur.fetchone()[0]
        logger.info("Wrote pipeline_runs row %s (status=%s)", run_id, status)
        return str(run_id)
    finally:
        conn.close()
