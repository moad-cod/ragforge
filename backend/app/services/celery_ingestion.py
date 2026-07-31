"""Compatibility imports for Celery ingestion tasks.

The worker task adapters now live in ``app.workers.tasks``.
"""

from app.workers.tasks import (
    bronze_to_silver_task,
    build_ingestion_workflow,
    detect_ingestion_plan_task,
    enqueue_ingestion,
    finalize_ingestion_task,
    silver_to_gold_task,
    upsert_qdrant_task,
)

__all__ = [
    "bronze_to_silver_task",
    "build_ingestion_workflow",
    "detect_ingestion_plan_task",
    "enqueue_ingestion",
    "finalize_ingestion_task",
    "silver_to_gold_task",
    "upsert_qdrant_task",
]
