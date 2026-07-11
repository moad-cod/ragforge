from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.repositories import ingestion_runs as ingestion_repository


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


def _run_payload(run) -> dict:
    return {
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


@router.get("/ingestion-runs/{ingestion_run_id}", dependencies=[Depends(require_pipeline_token)])
async def read_ingestion_run(
    ingestion_run_id: str,
    db: AsyncSession = Depends(get_db),
):
    run = await ingestion_repository.get_ingestion_run(db, ingestion_run_id)
    if run is None:
        raise HTTPException(404, "Ingestion run not found")
    return _run_payload(run)


@router.patch("/ingestion-runs/{ingestion_run_id}", dependencies=[Depends(require_pipeline_token)])
async def update_ingestion_run(
    ingestion_run_id: str,
    payload: PipelineStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    run = await ingestion_repository.update_ingestion_status(
        db,
        ingestion_run_id,
        payload.status,
        airflow_dag_run_id=payload.airflow_dag_run_id,
        error_message=payload.error_message,
    )
    if run is None:
        raise HTTPException(404, "Ingestion run not found")
    await db.commit()
    await db.refresh(run)
    return _run_payload(run)
