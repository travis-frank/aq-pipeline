-- Operational metadata for DAG runs. Written by Airflow directly — not a
-- dbt transform output. Apply with: make migrate

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dag_run_ts       timestamptz NOT NULL,
    rows_ingested    integer,
    rows_transformed integer,
    dbt_tests_run    integer,
    dbt_tests_passed integer,
    duration_seconds numeric,
    status           text CHECK (status IN ('success', 'failed')),
    error_message    text
);
