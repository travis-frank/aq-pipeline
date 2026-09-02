# Pipeline runtime deps for Airflow task execution (ingest, load, dbt).
FROM apache/airflow:2.9.3

USER airflow

COPY ingestion/requirements.txt /tmp/ingestion-requirements.txt
COPY pipeline/requirements.txt /tmp/pipeline-requirements.txt

RUN pip install --no-cache-dir \
    -r /tmp/ingestion-requirements.txt \
    -r /tmp/pipeline-requirements.txt
