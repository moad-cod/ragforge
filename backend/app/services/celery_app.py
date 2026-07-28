"""Celery application configuration for RAGForge ingestion workers."""

from __future__ import annotations

from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "ragforge",
    broker=settings.CELERY_BROKER_URL or None,
    backend=settings.CELERY_RESULT_BACKEND or None,
    include=["app.services.celery_ingestion"],
)

celery_app.conf.update(
    task_acks_late=True,
    task_track_started=True,
    task_reject_on_worker_lost=True,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=True,
    worker_prefetch_multiplier=settings.CELERY_WORKER_PREFETCH_MULTIPLIER,
    result_extended=True,
)
