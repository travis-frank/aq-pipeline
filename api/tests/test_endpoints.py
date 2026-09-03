"""API endpoint tests against local docker-compose Postgres."""

from __future__ import annotations

from datetime import date

import pytest


def test_air_quality_happy_path(client, known_station_id, db) -> None:
    response = client.get(f"/air-quality/{known_station_id}", params={"days": 365})

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) > 0

    with db.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM analytics_marts.mart_station_daily "
            "WHERE location_id = %s",
            (known_station_id,),
        )
        expected = cur.fetchone()[0]

    assert len(body) == expected

    first = body[0]
    assert first["location_id"] == known_station_id
    assert "measurement_date" in first
    assert "parameter" in first
    assert "avg_value" in first

    dates = [date.fromisoformat(row["measurement_date"]) for row in body]
    assert dates == sorted(dates, reverse=True)


def test_air_quality_nonexistent_station(client) -> None:
    response = client.get("/air-quality/999999999")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_air_quality_empty_window_returns_empty_list(
    client, known_station_id, db
) -> None:
    """Known station with no rows in the requested window → 200 [], not 404."""
    today = date.today()
    with db.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM analytics_marts.mart_station_daily "
            "WHERE location_id = %s AND measurement_date >= %s",
            (known_station_id, today),
        )
        today_rows = cur.fetchone()[0]

    if today_rows > 0:
        pytest.skip("mart has today's data — cannot assert empty window")

    response = client.get(
        f"/air-quality/{known_station_id}",
        params={"days": 1},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_pipeline_health_happy_path(client, db) -> None:
    with db.cursor() as cur:
        cur.execute("SELECT count(*) FROM pipeline_runs")
        if cur.fetchone()[0] == 0:
            pytest.skip("pipeline_runs is empty — run the DAG first")
        cur.execute(
            "SELECT run_id::text, status FROM pipeline_runs "
            "ORDER BY dag_run_ts DESC LIMIT 1"
        )
        run_id, status = cur.fetchone()

    response = client.get("/pipeline/health")

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id
    assert body["status"] == status
    assert "dag_run_ts" in body
    assert "rows_ingested" in body
    assert "dbt_tests_run" in body


def test_pipeline_health_empty_table(client, empty_pipeline_runs, db) -> None:
    with db.cursor() as cur:
        cur.execute("SELECT count(*) FROM pipeline_runs")
        assert cur.fetchone()[0] == 0

    response = client.get("/pipeline/health")

    assert response.status_code == 404
    assert "no pipeline runs" in response.json()["detail"].lower()


def test_pipeline_runs_restored_after_empty_test(db) -> None:
    """Sanity check: empty_pipeline_runs fixture restored history."""
    with db.cursor() as cur:
        cur.execute("SELECT count(*) FROM pipeline_runs")
        count = cur.fetchone()[0]
        cur.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' "
            "AND table_name = 'pipeline_runs__test_backup'"
        )
        backup_exists = cur.fetchone() is not None

    assert count >= 1
    assert not backup_exists
