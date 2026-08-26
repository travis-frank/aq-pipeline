.PHONY: up down psql load-raw dbt-debug migrate

ifneq (,$(wildcard ./.env))
include .env
export
endif

up:
	docker compose up -d

down:
	docker compose down

psql:
	docker compose exec postgres psql -U $(DB_USER) -d $(DB_NAME)

migrate:
	docker compose exec -T postgres psql -U $(DB_USER) -d $(DB_NAME) < pipeline/migrations/001_pipeline_runs.sql

load-raw:
	python pipeline/load_raw.py

dbt-debug:
	dbt debug --project-dir pipeline/dbt --profiles-dir pipeline/dbt
