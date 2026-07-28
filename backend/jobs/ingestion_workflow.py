"""Shared ingestion workflow stages for orchestrator adapters."""

from __future__ import annotations

from typing import Any

from app.services.pipeline_artifacts import (
    bronze_to_silver,
    gold_chunks,
    silver_to_gold,
)
from jobs.control_plane import RAGForgeControlPlane


IngestionPayload = dict[str, Any]


def _ingestion_run_id(ingestion: IngestionPayload) -> str:
    ingestion_run_id = str(ingestion.get("ingestion_run_id") or "").strip()
    if not ingestion_run_id:
        raise ValueError("Ingestion workflow payload has no ingestion_run_id")
    return ingestion_run_id


def detect_ingestion_plan(ingestion_run_id: str) -> IngestionPayload:
    client = RAGForgeControlPlane()
    run = client.get_run(ingestion_run_id)
    if run["status"] not in {"landed", "queued", "running"}:
        raise ValueError(f"Run cannot start from status {run['status']!r}")
    plan = run.get("ingestion_plan")
    if not plan:
        raise ValueError("Control plane did not return an ingestion plan")
    client.update_status(ingestion_run_id, "running")
    return {"ingestion_run_id": ingestion_run_id, "ingestion_plan": plan}


def bronze_to_silver_stage(ingestion: IngestionPayload) -> IngestionPayload:
    ingestion_run_id = _ingestion_run_id(ingestion)
    client = RAGForgeControlPlane()
    result = bronze_to_silver(client.get_run(ingestion_run_id))
    artifact_path = result.get("artifact_path")
    if not artifact_path:
        raise RuntimeError("Bronze-to-Silver job did not return artifact_path")
    client.update_status(
        ingestion_run_id,
        "silver_completed",
        silver_path=str(artifact_path),
    )
    return ingestion


def silver_to_gold_embed_stage(ingestion: IngestionPayload) -> IngestionPayload:
    ingestion_run_id = _ingestion_run_id(ingestion)
    client = RAGForgeControlPlane()
    result = silver_to_gold(client.get_run(ingestion_run_id))
    artifact_path = result.get("artifact_path")
    if not artifact_path:
        raise RuntimeError("Silver-to-Gold job did not return artifact_path")
    client.update_status(
        ingestion_run_id,
        "gold_completed",
        gold_path=str(artifact_path),
    )
    return ingestion


def upsert_qdrant_stage(ingestion: IngestionPayload) -> IngestionPayload:
    ingestion_run_id = _ingestion_run_id(ingestion)
    client = RAGForgeControlPlane()
    run = client.get_run(ingestion_run_id)
    client.index_chunks(ingestion_run_id, gold_chunks(run))
    return ingestion


def finalize_ingestion_stage(ingestion: IngestionPayload) -> IngestionPayload:
    RAGForgeControlPlane().update_status(_ingestion_run_id(ingestion), "indexed")
    return ingestion


def mark_ingestion_failed(ingestion_run_id: str, error_message: str) -> None:
    RAGForgeControlPlane().update_status(
        ingestion_run_id,
        "failed",
        error_message=error_message,
    )
