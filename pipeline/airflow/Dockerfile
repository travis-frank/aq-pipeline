# Pipeline runtime for Airflow on Fargate (and local compose).
# Bake ingestion + pipeline code into the image. Fargate has no bind mounts.

FROM apache/airflow:2.9.3

USER root

COPY ingestion/requirements.txt /tmp/ingestion-requirements.txt
COPY pipeline/requirements.txt /tmp/pipeline-requirements.txt

# Application code the DAG imports and runs (ingest, load_raw, dbt, locations).
COPY ingestion /opt/aq-pipeline/ingestion
COPY pipeline /opt/aq-pipeline/pipeline

# Env-based dbt profile (no secrets in the image).
COPY pipeline/dbt/profiles.yml.example /opt/aq-pipeline/pipeline/dbt/profiles.yml

# Standard Airflow DAGs folder (compose also bind-mounts this path locally).
RUN mkdir -p /opt/airflow/dags \
  && cp -a /opt/aq-pipeline/pipeline/dags/. /opt/airflow/dags/ \
  && chown -R airflow:root /opt/aq-pipeline /opt/airflow/dags

USER airflow

RUN pip install --no-cache-dir \
    -r /tmp/ingestion-requirements.txt \
    -r /tmp/pipeline-requirements.txt

ENV AIRFLOW_REPO_ROOT=/opt/aq-pipeline
ENV DBT_PROFILES_DIR=/opt/aq-pipeline/pipeline/dbt
