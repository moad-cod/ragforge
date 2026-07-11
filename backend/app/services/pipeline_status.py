"""Database boundary used by Airflow/Spark ingestion jobs."""
import asyncio

from app.core.db import AsyncSessionLocal
from app.repositories.ingestion_runs import (
    get_ingestion_run,
    mark_ingestion_failed,
    update_ingestion_status,
)


async def read_ingestion_run(ingestion_run_id: str) -> dict | None:
    async with AsyncSessionLocal() as db:
        run = await get_ingestion_run(db, ingestion_run_id)
        if run is None:
            return None
        return {
            "id": run.id,
            "project_id": run.project_id,
            "document_id": run.document_id,
            "document_version_id": run.document_version_id,
            "status": run.status,
            "airflow_dag_run_id": run.airflow_dag_run_id,
        }


async def record_pipeline_status(
    ingestion_run_id: str,
    status: str,
    *,
    airflow_dag_run_id: str | None = None,
    error_message: str | None = None,
) -> None:
    async with AsyncSessionLocal() as db:
        run = await update_ingestion_status(
            db,
            ingestion_run_id,
            status,
            airflow_dag_run_id=airflow_dag_run_id,
            error_message=error_message,
        )
        if run is None:
            raise LookupError(f"Ingestion run {ingestion_run_id} does not exist")
        await db.commit()


async def record_pipeline_failure(ingestion_run_id: str, error_message: str) -> None:
    async with AsyncSessionLocal() as db:
        run = await mark_ingestion_failed(db, ingestion_run_id, error_message)
        if run is None:
            raise LookupError(f"Ingestion run {ingestion_run_id} does not exist")
        await db.commit()


def read_ingestion_run_sync(ingestion_run_id: str) -> dict | None:
    return asyncio.run(read_ingestion_run(ingestion_run_id))


def record_pipeline_status_sync(
    ingestion_run_id: str,
    status: str,
    airflow_dag_run_id: str | None = None,
) -> None:
    asyncio.run(
        record_pipeline_status(
            ingestion_run_id,
            status,
            airflow_dag_run_id=airflow_dag_run_id,
        )
    )


def record_pipeline_failure_sync(ingestion_run_id: str, error_message: str) -> None:
    asyncio.run(record_pipeline_failure(ingestion_run_id, error_message))
