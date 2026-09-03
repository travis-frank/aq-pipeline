"""FastAPI service over the air-quality warehouse."""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import psycopg2
from fastapi import FastAPI, HTTPException, Query, Response, status
from psycopg2.extras import RealDictCursor

from api.schemas import PipelineRunHealth, StationDailyReading

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
MART_TABLE = "analytics_marts.mart_station_daily"

app = FastAPI(title="aq-pipeline API", version="0.1.0")


def load_dotenv(path: Path = ENV_FILE) -> None:
    """Load KEY=VALUE pairs from .env without overwriting existing env vars."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def db_connect():
    """Connect using DB_* variables."""
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


def _station_exists(conn, station_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT 1 FROM {MART_TABLE} WHERE location_id = %s LIMIT 1",
            (station_id,),
        )
        return cur.fetchone() is not None


@app.on_event("startup")
def startup() -> None:
    load_dotenv()


@app.get("/health")
def health(response: Response) -> dict[str, str]:
    """Confirm the API can reach the warehouse Postgres."""
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
    except (RuntimeError, psycopg2.Error) as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unhealthy", "database": str(exc)}

    return {"status": "ok", "database": "connected"}


@app.get("/air-quality/{station_id}", response_model=list[StationDailyReading])
def air_quality(
    station_id: int,
    days: int = Query(default=14, ge=1, le=365, description="Lookback window in days"),
) -> list[StationDailyReading]:
    """Daily readings for a station from mart_station_daily (one row per day/pollutant)."""
    since = date.today() - timedelta(days=days - 1)

    try:
        with db_connect() as conn:
            if not _station_exists(conn, station_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Station {station_id} not found",
                )

            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    f"""
                    SELECT
                        location_id,
                        location_name,
                        measurement_date,
                        parameter,
                        units,
                        record_count,
                        flagged_count,
                        unflagged_count,
                        min_value,
                        max_value,
                        avg_value,
                        coverage_pct,
                        latitude,
                        longitude,
                        last_pulled_at
                    FROM {MART_TABLE}
                    WHERE location_id = %s
                      AND measurement_date >= %s
                    ORDER BY measurement_date DESC, parameter ASC
                    """,
                    (station_id, since),
                )
                rows = cur.fetchall()
    except HTTPException:
        raise
    except (RuntimeError, psycopg2.Error) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return [StationDailyReading.model_validate(row) for row in rows]


@app.get("/pipeline/health", response_model=PipelineRunHealth)
def pipeline_health() -> PipelineRunHealth:
    """Most recent row from pipeline_runs."""
    try:
        with db_connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        run_id,
                        dag_run_ts,
                        rows_ingested,
                        rows_transformed,
                        dbt_tests_run,
                        dbt_tests_passed,
                        duration_seconds,
                        status,
                        error_message
                    FROM pipeline_runs
                    ORDER BY dag_run_ts DESC
                    LIMIT 1
                    """
                )
                row = cur.fetchone()
    except (RuntimeError, psycopg2.Error) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pipeline runs recorded",
        )

    return PipelineRunHealth.model_validate(row)
