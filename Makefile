.PHONY: up down psql

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
