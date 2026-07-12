"""Airflow orchestration shell for the RAGForge ingestion data-plane jobs."""
from datetime import datetime
import os
import shlex
import subprocess

from airflow.sdk import dag, get_current_context, task

from ragforge_control_plane import (
    RAGForgeControlPlane,
    ingestion_run_id_from_context,
    mark_task_failure,
    record_task_status,
)


def _run_configured_job(environment_name: str, ingestion_run_id: str) -> None:
    command_template = os.environ.get(environment_name, "").strip()
    if not command_template:
        raise RuntimeError(f"{environment_name} must be configured for the ingestion DAG")
    command = command_template.format(ingestion_run_id=ingestion_run_id)
    subprocess.run(shlex.split(command), check=True)


@dag(
    dag_id="ragforge_ingestion",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=4,
    on_failure_callback=mark_task_failure,
    tags=["ragforge", "ingestion"],
)
def ragforge_ingestion():
    @task(on_failure_callback=mark_task_failure)
    def validate_bronze() -> str:
        context = get_current_context()
        ingestion_run_id = ingestion_run_id_from_context(context)
        run = RAGForgeControlPlane().get_run(ingestion_run_id)
        if run["status"] not in {"landed", "queued", "running"}:
            raise ValueError(f"Run cannot start from status {run['status']!r}")
        record_task_status(context, "running")
        return ingestion_run_id

    @task(on_failure_callback=mark_task_failure)
    def bronze_to_silver_spark(ingestion_run_id: str) -> str:
        _run_configured_job("RAGFORGE_BRONZE_TO_SILVER_CMD", ingestion_run_id)
        record_task_status(get_current_context(), "silver_completed")
        return ingestion_run_id

    @task(on_failure_callback=mark_task_failure)
    def silver_to_gold_embed(ingestion_run_id: str) -> str:
        _run_configured_job("RAGFORGE_SILVER_TO_GOLD_CMD", ingestion_run_id)
        record_task_status(get_current_context(), "gold_completed")
        return ingestion_run_id

    @task(on_failure_callback=mark_task_failure)
    def upsert_qdrant(ingestion_run_id: str) -> str:
        _run_configured_job("RAGFORGE_UPSERT_QDRANT_CMD", ingestion_run_id)
        return ingestion_run_id

    @task(on_failure_callback=mark_task_failure)
    def update_postgres_status(ingestion_run_id: str) -> None:
        record_task_status(get_current_context(), "indexed")

    bronze = validate_bronze()
    silver = bronze_to_silver_spark(bronze)
    gold = silver_to_gold_embed(silver)
    indexed = upsert_qdrant(gold)
    update_postgres_status(indexed)


ragforge_ingestion()
