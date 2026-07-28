"""Orchestrator-neutral ingestion enqueue boundary."""

from __future__ import annotations

from app.core.config import settings


def selected_orchestrator() -> str:
    return settings.ORCHESTRATOR.strip().lower()


def ingestion_orchestration_enabled() -> bool:
    orchestrator = selected_orchestrator()
    if orchestrator == "airflow":
        return bool(settings.AIRFLOW_API_URL)
    if orchestrator == "celery":
        return bool(settings.CELERY_BROKER_URL or settings.CELERY_TASK_ALWAYS_EAGER)
    return False


async def enqueue_ingestion(ingestion_run_id: str) -> str | None:
    orchestrator = selected_orchestrator()
    if orchestrator == "celery":
        from app.services.celery_ingestion import enqueue_ingestion as enqueue_celery

        return await enqueue_celery(ingestion_run_id)
    if orchestrator == "airflow":
        from app.services.airflow import enqueue_ingestion as enqueue_airflow

        return await enqueue_airflow(ingestion_run_id)
    return None
