# syntax=docker/dockerfile:1.7

ARG AIRFLOW_BASE_IMAGE=apache/airflow:3.3.0
FROM ${AIRFLOW_BASE_IMAGE}

ENV PIP_DEFAULT_TIMEOUT=180 \
    PIP_RETRIES=10 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY airflow/pipeline-requirements.txt /tmp/ragforge-pipeline-requirements.txt
RUN --mount=type=cache,target=/tmp/pip-cache,uid=50000,gid=0 \
    python -m pip install \
        --cache-dir /tmp/pip-cache \
        --prefer-binary \
        -r /tmp/ragforge-pipeline-requirements.txt
