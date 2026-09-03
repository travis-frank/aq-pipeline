"""Shared fixtures for API tests against local Postgres."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app, db_connect, load_dotenv


@pytest.fixture(scope="session", autouse=True)
def _load_env() -> None:
    load_dotenv()


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient using the same DB_* env vars as the rest of the project."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db():
    """Direct warehouse connection for setup / assertions."""
    conn = db_connect()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def known_station_id(db) -> int:
    """A location_id that exists in mart_station_daily."""
    with db.cursor() as cur:
        cur.execute(
            "SELECT location_id FROM analytics_marts.mart_station_daily "
            "ORDER BY location_id LIMIT 1"
        )
        row = cur.fetchone()
    if row is None:
        pytest.skip("mart_station_daily is empty — run the pipeline first")
    return int(row[0])


@pytest.fixture
def empty_pipeline_runs(db):
    """Temporarily empty pipeline_runs without destroying history.

    Moves existing rows into a backup table for the duration of the test,
    then restores them. A transaction alone would not work: the API opens
    its own connection and would still see committed rows.
    """
    backup = "pipeline_runs__test_backup"
    with db:
        with db.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {backup}")
            cur.execute(
                f"CREATE TABLE {backup} (LIKE pipeline_runs INCLUDING ALL)"
            )
            cur.execute(f"INSERT INTO {backup} SELECT * FROM pipeline_runs")
            cur.execute("DELETE FROM pipeline_runs")

    try:
        yield
    finally:
        with db:
            with db.cursor() as cur:
                cur.execute("DELETE FROM pipeline_runs")
                cur.execute(
                    f"INSERT INTO pipeline_runs SELECT * FROM {backup}"
                )
                cur.execute(f"DROP TABLE IF EXISTS {backup}")
