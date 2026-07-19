"""Airflow orchestration shell for the RAGForge ingestion data-plane jobs."""
from datetime import datetime, timedelta
import json
import logging
import os
import shlex
import subprocess

from airflow.sdk import dag, get_current_context, task
from jobs.ingestion_execution import build_job_environment, profile_environment_name

from ragforge_control_plane import (
    RAGForgeControlPlane,
    ingestion_run_id_from_context,
    mark_task_failure,
    record_task_status,
)

logger = logging.getLogger(__name__)


def _run_configured_job(
    environment_name: str,
    ingestion: dict,
) -> dict:
    ingestion_run_id = ingestion["ingestion_run_id"]
    plan = ingestion["ingestion_plan"]
    selected_environment = profile_environment_name(environment_name, plan)
    command_template = os.environ.get(selected_environment, "").strip()
    if not command_template:
        raise RuntimeError(f"{environment_name} must be configured for the ingestion DAG")
    command = command_template.format(
        ingestion_run_id=ingestion_run_id,
        profile=plan["profile"],
        chunker_id=plan["technique_id"],
        source_type=plan["source_type"],
    )
    job_environment = build_job_environment(plan)
    logger.info(
        "Running %s with profile=%s technique=%s resource_class=%s batch_size=%s",
        selected_environment,
        plan["profile"],
        plan["technique_id"],
        plan["resource_class"],
        plan["embedding_batch_size"],
    )
    try:
        completed = subprocess.run(
            shlex.split(command),
            check=True,
            capture_output=True,
            text=True,
            env=job_environment,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(f"{environment_name} failed with exit code {exc.returncode}{suffix}") from exc
    if completed.stderr.strip():
        logger.info("%s stderr:\n%s", environment_name, completed.stderr.rstrip())
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"{environment_name} did not return a JSON result")
    try:
        result = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{environment_name} returned invalid JSON: {lines[-1]!r}") from exc
    logger.info("%s result: %s", environment_name, result)
    return result


@dag(
    dag_id="ragforge_ingestion",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=4,
    default_args={"retries": 2, "retry_delay": timedelta(seconds=10)},
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
        result = _run_configured_job("RAGFORGE_BRONZE_TO_SILVER_CMD", ingestion_run_id)
        artifact_path = result.get("artifact_path")
        if not artifact_path:
            raise RuntimeError("Bronze-to-Silver job did not return artifact_path")
        record_task_status(
            get_current_context(),
            "silver_completed",
            silver_path=artifact_path,
        )
        return ingestion_run_id

    @task(on_failure_callback=mark_task_failure)
    def silver_to_gold_embed(ingestion_run_id: str) -> str:
        result = _run_configured_job("RAGFORGE_SILVER_TO_GOLD_CMD", ingestion_run_id)
        artifact_path = result.get("artifact_path")
        if not artifact_path:
            raise RuntimeError("Silver-to-Gold job did not return artifact_path")
        record_task_status(
            get_current_context(),
            "gold_completed",
            gold_path=artifact_path,
        )
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
