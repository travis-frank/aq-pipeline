"""Pydantic response models for the aq-pipeline API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class StationDailyReading(BaseModel):
    location_id: int
    location_name: str
    measurement_date: date
    parameter: str
    units: str
    record_count: int
    flagged_count: int
    unflagged_count: int
    min_value: float | None
    max_value: float | None
    avg_value: float | None
    coverage_pct: float | None
    latitude: float | None
    longitude: float | None
    last_pulled_at: datetime | None


class PipelineRunHealth(BaseModel):
    run_id: UUID
    dag_run_ts: datetime
    rows_ingested: int | None
    rows_transformed: int | None
    dbt_tests_run: int | None
    dbt_tests_passed: int | None
    duration_seconds: float | None
    status: Literal["success", "failed"]
    error_message: str | None = None
