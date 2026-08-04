"""Celery ingestion orchestration for the RAGForge batch pipeline."""

from __future__ import annotations

import logging
from typing import Any

from celery import chain

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.repositories.ingestion_runs import update_ingestion_status
from app.workers.celery_app import celery_app
from app.services.event_stream import publish_ingestion_event
from jobs.control_plane import RAGForgeControlPlane
from jobs.ingestion_workflow import (
    bronze_to_silver_stage,
    detect_ingestion_plan,
    finalize_ingestion_stage,
    mark_ingestion_failed,
    silver_to_gold_embed_stage,
    upsert_qdrant_stage,
)


logger = logging.getLogger(__name__)


def _run_id_from_payload(payload: dict[str, Any] | str) -> str:
    if isinstance(payload, str):
        return payload
    return str(payload.get("ingestion_run_id") or "")


def _handle_stage_error(task, ingestion_run_id: str, exc: Exception):
    max_retries = task.max_retries or 0
    if task.request.retries >= max_retries:
        try:
            mark_ingestion_failed(ingestion_run_id, str(exc))
        except Exception:
            logger.exception("Could not mark ingestion run %s as failed", ingestion_run_id)
        raise exc
    if getattr(task, "name", "") == "ragforge.ingestion.silver_to_gold":
        try:
            client = RAGForgeControlPlane()
            run = client.get_run(ingestion_run_id)
            client.update_embedding_progress(
                ingestion_run_id,
                {
                    "stage": "retrying",
                    "embedding_model": run.get("embedding_model") or settings.EMBEDDING_MODEL,
                    "total_chunks": 0,
                    "embedded_chunks": 0,
                    "attempt": task.request.retries + 2,
                    "error_message": str(exc),
                },
            )
        except Exception:
            logger.exception("Could not mark embedding run %s as retrying", ingestion_run_id)
    raise task.retry(
        exc=exc,
        countdown=settings.CELERY_TASK_RETRY_DELAY_SECONDS,
    )


def _task_options() -> dict[str, Any]:
    return {
        "bind": True,
        "max_retries": settings.CELERY_TASK_MAX_RETRIES,
        "default_retry_delay": settings.CELERY_TASK_RETRY_DELAY_SECONDS,
    }


def _embedding_task_options() -> dict[str, Any]:
    options = _task_options()
    if settings.EMBEDDING_TIMEOUT_SECONDS > 0:
        soft_limit = int(settings.EMBEDDING_TIMEOUT_SECONDS)
        options["soft_time_limit"] = soft_limit
        options["time_limit"] = soft_limit + 30
    return options


@celery_app.task(name="ragforge.ingestion.detect_plan", **_task_options())
def detect_ingestion_plan_task(self, ingestion_run_id: str) -> dict[str, Any]:
    try:
        return detect_ingestion_plan(ingestion_run_id)
    except Exception as exc:
        return _handle_stage_error(self, ingestion_run_id, exc)


@celery_app.task(name="ragforge.ingestion.bronze_to_silver", **_task_options())
def bronze_to_silver_task(self, ingestion: dict[str, Any]) -> dict[str, Any]:
    ingestion_run_id = _run_id_from_payload(ingestion)
    try:
        return bronze_to_silver_stage(ingestion)
    except Exception as exc:
        return _handle_stage_error(self, ingestion_run_id, exc)


@celery_app.task(name="ragforge.ingestion.silver_to_gold", **_embedding_task_options())
def silver_to_gold_task(self, ingestion: dict[str, Any]) -> dict[str, Any]:
    ingestion_run_id = _run_id_from_payload(ingestion)
    try:
        return silver_to_gold_embed_stage(ingestion)
    except Exception as exc:
        return _handle_stage_error(self, ingestion_run_id, exc)


@celery_app.task(name="ragforge.ingestion.upsert_qdrant", **_task_options())
def upsert_qdrant_task(self, ingestion: dict[str, Any]) -> dict[str, Any]:
    ingestion_run_id = _run_id_from_payload(ingestion)
    try:
        return upsert_qdrant_stage(ingestion)
    except Exception as exc:
        return _handle_stage_error(self, ingestion_run_id, exc)


@celery_app.task(name="ragforge.ingestion.finalize", **_task_options())
def finalize_ingestion_task(self, ingestion: dict[str, Any]) -> dict[str, Any]:
    ingestion_run_id = _run_id_from_payload(ingestion)
    try:
        return finalize_ingestion_stage(ingestion)
    except Exception as exc:
        return _handle_stage_error(self, ingestion_run_id, exc)


def build_ingestion_workflow(ingestion_run_id: str):
    return chain(
        detect_ingestion_plan_task.s(ingestion_run_id),
        bronze_to_silver_task.s(),
        silver_to_gold_task.s(),
        upsert_qdrant_task.s(),
        finalize_ingestion_task.s(),
    )


async def enqueue_ingestion(ingestion_run_id: str) -> str | None:
    """Publish the Celery ingestion chain and persist its workflow ID."""
    if not settings.CELERY_BROKER_URL and not settings.CELERY_TASK_ALWAYS_EAGER:
        return None

    try:
        result = build_ingestion_workflow(ingestion_run_id).apply_async()
        workflow_id = str(result.id)
        async with AsyncSessionLocal() as db:
            await update_ingestion_status(
                db,
                ingestion_run_id,
                "queued",
                airflow_dag_run_id=workflow_id,
            )
            await db.commit()
        await publish_ingestion_event(
            ingestion_run_id,
            "queued",
            data={"airflow_dag_run_id": workflow_id},
        )
        return workflow_id
    except Exception:
        logger.exception("Could not enqueue ingestion run %s in Celery", ingestion_run_id)
        return None
