.PHONY: up down psql load-raw dbt-debug migrate

ifneq (,$(wildcard ./.env))
include .env
export
endif

up:
	docker compose up -d postgres
	@echo "Waiting for Postgres..."
	@until docker compose exec -T postgres pg_isready -U $(DB_USER) -d $(DB_NAME) >/dev/null 2>&1; do sleep 1; done
	$(MAKE) migrate
	docker compose up -d

down:
	docker compose down

psql:
	docker compose exec postgres psql -U $(DB_USER) -d $(DB_NAME)

migrate:
	docker compose exec -T postgres psql -U $(DB_USER) -d $(DB_NAME) < pipeline/migrations/001_pipeline_runs.sql
	bash pipeline/migrations/002_airflow_database.sh

load-raw:
	python pipeline/load_raw.py

dbt-debug:
	dbt debug --project-dir pipeline/dbt --profiles-dir pipeline/dbt
