ARG AIRFLOW_BASE_IMAGE=apache/airflow:3.3.0
FROM ${AIRFLOW_BASE_IMAGE}

COPY airflow/pipeline-requirements.txt /tmp/ragforge-pipeline-requirements.txt
RUN pip install --no-cache-dir -r /tmp/ragforge-pipeline-requirements.txt
