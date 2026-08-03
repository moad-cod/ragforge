"""Orchestrator-neutral ingestion enqueue boundary."""

from __future__ import annotations

import logging

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.repositories.ingestion_runs import mark_ingestion_failed
from app.services.event_stream import publish_ingestion_event


logger = logging.getLogger(__name__)
DISPATCH_FAILURE_MESSAGE = (
    "Ingestion orchestration failed to start. Verify the configured "
    "Airflow or Celery service is reachable, then retry the run."
)


def selected_orchestrator() -> str:
    return settings.ORCHESTRATOR.strip().lower()


def ingestion_orchestration_enabled() -> bool:
    orchestrator = selected_orchestrator()
    if orchestrator == "airflow":
        return bool(settings.AIRFLOW_API_URL)
    if orchestrator == "celery":
        return bool(settings.CELERY_BROKER_URL or settings.CELERY_TASK_ALWAYS_EAGER)
    return False


async def mark_ingestion_dispatch_failed(
    ingestion_run_id: str,
    error_message: str = DISPATCH_FAILURE_MESSAGE,
) -> None:
    """Persist a terminal state when the selected orchestrator never accepts a run."""
    async with AsyncSessionLocal() as db:
        run = await mark_ingestion_failed(db, ingestion_run_id, error_message)
        if run is None:
            logger.warning("Could not mark missing ingestion run %s as failed", ingestion_run_id)
            return
        await db.commit()
    await publish_ingestion_event(
        ingestion_run_id,
        "failed",
        data={"error_message": error_message},
    )


async def enqueue_ingestion(ingestion_run_id: str) -> str | None:
    if not ingestion_orchestration_enabled():
        return None
    orchestrator = selected_orchestrator()
    workflow_id: str | None = None
    try:
        if orchestrator == "celery":
            from app.workers.tasks import enqueue_ingestion as enqueue_celery

            workflow_id = await enqueue_celery(ingestion_run_id)
        elif orchestrator == "airflow":
            from app.services.airflow import enqueue_ingestion as enqueue_airflow

            workflow_id = await enqueue_airflow(ingestion_run_id)
    except Exception:
        logger.exception(
            "Configured %s orchestrator failed while accepting ingestion run %s",
            orchestrator,
            ingestion_run_id,
        )
        await mark_ingestion_dispatch_failed(ingestion_run_id)
        raise

    if workflow_id:
        return workflow_id

    logger.error(
        "Configured %s orchestrator did not accept ingestion run %s",
        orchestrator,
        ingestion_run_id,
    )
    await mark_ingestion_dispatch_failed(ingestion_run_id)
    return None
