# Creates the Airflow metastore database on the shared Postgres instance.
# Warehouse data (raw/staging/marts/pipeline_runs) stays in aq_pipeline.
# Safe to re-run
set -euo pipefail

DB_USER="${DB_USER:?DB_USER is required}"
AIRFLOW_DB_NAME="${AIRFLOW_DB_NAME:-airflow}"

exists="$(
  docker compose exec -T postgres \
    psql -U "${DB_USER}" -d postgres -Atc \
    "SELECT 1 FROM pg_database WHERE datname = '${AIRFLOW_DB_NAME}'"
)"

if [[ "${exists}" == "1" ]]; then
  echo "Database '${AIRFLOW_DB_NAME}' already exists — skipping."
  exit 0
fi

docker compose exec -T postgres \
  psql -U "${DB_USER}" -d postgres \
  -c "CREATE DATABASE ${AIRFLOW_DB_NAME} OWNER ${DB_USER};"

echo "Created database '${AIRFLOW_DB_NAME}'."
