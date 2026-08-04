from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.models import Document, DocumentVersion, Project
from app.repositories import embedding_runs as embedding_repository
from app.repositories import ingestion_runs as ingestion_repository
from app.services.chunk_indexing import GoldChunk, index_document_version_chunks
from app.services.event_stream import publish_ingestion_event
from app.services.ingestion_planner import build_ingestion_plan


router = APIRouter()


def require_pipeline_token(authorization: str | None = Header(default=None)) -> None:
    if not settings.PIPELINE_SERVICE_TOKEN:
        raise HTTPException(503, "Pipeline service authentication is not configured")
    if authorization != f"Bearer {settings.PIPELINE_SERVICE_TOKEN}":
        raise HTTPException(401, "Invalid pipeline service token")


class PipelineStatusUpdate(BaseModel):
    status: Literal[
        "landed",
        "queued",
        "running",
        "silver_completed",
        "gold_completed",
        "indexed",
        "failed",
        "cancelled",
    ]
    airflow_dag_run_id: str | None = None
    error_message: str | None = None
    silver_path: str | None = None
    gold_path: str | None = None


class GoldChunkPayload(BaseModel):
    chunk_index: int
    text: str
    dense_vector: list[float]
    content_hash: str | None = None
    token_count: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    section_title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IndexChunksPayload(BaseModel):
    chunks: list[GoldChunkPayload]


class EmbeddingProgressUpdate(BaseModel):
    stage: Literal["queued", "loading_model", "running", "retrying", "completed", "failed"]
    embedding_model: str
    embedding_batch_size: int | None = None
    total_chunks: int = 0
    embedded_chunks: int = 0
    total_batches: int | None = None
    embedded_batches: int | None = None
    elapsed_ms: int | None = None
    last_heartbeat_at: str | None = None
    embedding_backend: str | None = None
    embedding_device: str | None = None
    embedding_dimension: int | None = None
    model_load_elapsed_ms: int | None = None
    attempt: int | None = None
    error_code: str | None = None
    error_message: str | None = None


def _embedding_status(stage: str) -> str:
    return stage


def _embedding_progress_payload(run, payload: EmbeddingProgressUpdate) -> dict[str, Any]:
    return {
        "stage": payload.stage,
        "embedding_model": payload.embedding_model,
        "embedding_batch_size": payload.embedding_batch_size,
        "total_chunks": payload.total_chunks,
        "embedded_chunks": payload.embedded_chunks,
        "total_batches": payload.total_batches,
        "embedded_batches": payload.embedded_batches,
        "elapsed_ms": payload.elapsed_ms,
        "last_heartbeat_at": payload.last_heartbeat_at,
        "embedding_backend": payload.embedding_backend,
        "embedding_device": payload.embedding_device,
        "embedding_dimension": payload.embedding_dimension,
        "model_load_elapsed_ms": payload.model_load_elapsed_ms,
        "attempt": payload.attempt,
        "error_code": payload.error_code,
        "error_message": payload.error_message,
        "document_id": run.document_id,
        "document_version_id": run.document_version_id,
    }


def _parse_heartbeat(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).replace(tzinfo=None)
    except ValueError:
        return None


def _run_payload(run, *, project=None, document=None, version=None) -> dict:
    payload = {
        "ingestion_run_id": run.id,
        "project_id": run.project_id,
        "document_id": run.document_id,
        "document_version_id": run.document_version_id,
        "status": run.status,
        "airflow_dag_run_id": run.airflow_dag_run_id,
        "error_message": run.error_message,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "created_at": run.created_at,
    }
    if project is not None:
        payload.update(
            {
                "organization_id": project.organization_id,
                "qdrant_collection": project.qdrant_collection,
            }
        )
    if document is not None:
        payload.update(
            {
                "filename": document.filename,
                "source_type": document.source_type,
                "mime_type": document.mime_type,
            }
        )
    if version is not None:
        ingestion_plan = build_ingestion_plan(
            version.chunker_id,
            source_type=document.source_type if document is not None else None,
        )
        payload.update(
            {
                "version_number": version.version_number,
                "bronze_path": version.bronze_path,
                "silver_path": version.silver_path,
                "gold_path": version.gold_path,
                "parser_name": version.parser_name,
                "chunker_id": version.chunker_id,
                "embedding_model": version.embedding_model,
                "embedding_dimension": settings.EMBEDDING_DIMENSION,
                "ingestion_plan": ingestion_plan.as_dict(),
            }
        )
    return payload


@router.get("/ingestion-runs/{ingestion_run_id}", dependencies=[Depends(require_pipeline_token)])
async def read_ingestion_run(
    ingestion_run_id: str,
    db: AsyncSession = Depends(get_db),
):
    run = await ingestion_repository.get_ingestion_run(db, ingestion_run_id)
    if run is None:
        raise HTTPException(404, "Ingestion run not found")
    project = await db.get(Project, run.project_id)
    document = await db.get(Document, run.document_id)
    version = await db.get(DocumentVersion, run.document_version_id)
    if project is None or document is None or version is None:
        raise HTTPException(409, "Ingestion run lineage is incomplete")
    return _run_payload(run, project=project, document=document, version=version)


@router.patch("/ingestion-runs/{ingestion_run_id}", dependencies=[Depends(require_pipeline_token)])
async def update_ingestion_run(
    ingestion_run_id: str,
    payload: PipelineStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        run = await ingestion_repository.update_ingestion_status(
            db,
            ingestion_run_id,
            payload.status,
            airflow_dag_run_id=payload.airflow_dag_run_id,
            error_message=payload.error_message,
            silver_path=payload.silver_path,
            gold_path=payload.gold_path,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    if run is None:
        raise HTTPException(404, "Ingestion run not found")
    await db.commit()
    await db.refresh(run)
    await publish_ingestion_event(
        run.id,
        run.status,
        data={
            "document_id": run.document_id,
            "document_version_id": run.document_version_id,
            "airflow_dag_run_id": run.airflow_dag_run_id,
            "error_message": run.error_message,
        },
    )
    return _run_payload(run)


@router.patch(
    "/ingestion-runs/{ingestion_run_id}/embedding-progress",
    dependencies=[Depends(require_pipeline_token)],
)
async def update_ingestion_run_embedding_progress(
    ingestion_run_id: str,
    payload: EmbeddingProgressUpdate,
    db: AsyncSession = Depends(get_db),
):
    run = await ingestion_repository.get_ingestion_run(db, ingestion_run_id)
    if run is None:
        raise HTTPException(404, "Ingestion run not found")
    if run.status not in {"running", "silver_completed", "gold_completed", "indexed"}:
        raise HTTPException(409, f"Embedding progress cannot be recorded from status {run.status!r}")

    project = await db.get(Project, run.project_id)
    version = await db.get(DocumentVersion, run.document_version_id)
    if project is None or version is None:
        raise HTTPException(409, "Ingestion run lineage is incomplete")

    embedding_run = await embedding_repository.upsert_embedding_progress(
        db,
        project_id=run.project_id,
        document_version_id=run.document_version_id,
        embedding_model=payload.embedding_model,
        status=_embedding_status(payload.stage),
        total_chunks=payload.total_chunks,
        embedded_chunks=payload.embedded_chunks,
        total_batches=payload.total_batches,
        embedded_batches=payload.embedded_batches,
        batch_size=payload.embedding_batch_size,
        embedding_backend=payload.embedding_backend,
        embedding_device=payload.embedding_device,
        embedding_dimension=payload.embedding_dimension,
        attempt=payload.attempt,
        last_heartbeat_at=_parse_heartbeat(payload.last_heartbeat_at),
        error_code=payload.error_code,
        error_message=payload.error_message,
    )
    await db.commit()
    progress = _embedding_progress_payload(run, payload)
    await publish_ingestion_event(
        run.id,
        "running",
        data={
            "document_id": run.document_id,
            "document_version_id": run.document_version_id,
            "embedding_run_id": embedding_run.id,
            "embedding_progress": progress,
        },
    )
    return {"embedding_run_id": embedding_run.id, "embedding_progress": progress}


@router.post(
    "/ingestion-runs/{ingestion_run_id}/chunks/index",
    dependencies=[Depends(require_pipeline_token)],
)
async def index_ingestion_run_chunks(
    ingestion_run_id: str,
    payload: IndexChunksPayload,
    db: AsyncSession = Depends(get_db),
):
    """Persist Gold chunk lineage and idempotently rebuild its Qdrant points."""
    run = await ingestion_repository.get_ingestion_run(db, ingestion_run_id)
    if run is None:
        raise HTTPException(404, "Ingestion run not found")
    if run.status not in {"gold_completed", "indexed"}:
        raise HTTPException(409, f"Chunks cannot be indexed from status {run.status!r}")

    project = await db.get(Project, run.project_id)
    document = await db.get(Document, run.document_id)
    version = await db.get(DocumentVersion, run.document_version_id)
    if project is None or document is None or version is None:
        raise HTTPException(409, "Ingestion run lineage is incomplete")

    try:
        records = await index_document_version_chunks(
            db,
            project=project,
            document=document,
            version=version,
            ingestion_run=run,
            chunks=[GoldChunk(**chunk.model_dump()) for chunk in payload.chunks],
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    await db.commit()
    return {
        "ingestion_run_id": run.id,
        "document_version_id": version.id,
        "qdrant_collection": project.qdrant_collection,
        "chunks_indexed": len(records),
    }
