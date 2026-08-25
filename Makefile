.PHONY: up down psql load-raw dbt-debug

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

load-raw:
	python pipeline/load_raw.py

dbt-debug:
	dbt debug --project-dir pipeline/dbt --profiles-dir pipeline/dbt
