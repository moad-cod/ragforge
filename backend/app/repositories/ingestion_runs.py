from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, DocumentVersion, IngestionRun


TERMINAL_STATUSES = frozenset({"indexed", "failed", "cancelled"})
DOCUMENT_STATUS_BY_RUN_STATUS = {
    "landed": "landed",
    "queued": "landed",
    "running": "processing",
    "silver_completed": "chunked",
    "gold_completed": "embedded",
    "indexed": "indexed",
    "failed": "failed",
    "cancelled": "failed",
}


async def create_ingestion_run(db: AsyncSession, **values) -> IngestionRun:
    run = IngestionRun(**values)
    db.add(run)
    await db.flush()
    return run


async def get_ingestion_run(db: AsyncSession, ingestion_run_id: str) -> IngestionRun | None:
    return await db.get(IngestionRun, ingestion_run_id)


async def get_owned_ingestion_run(
    db: AsyncSession,
    ingestion_run_id: str,
    user_id: str,
) -> IngestionRun | None:
    result = await db.execute(
        select(IngestionRun).where(
            IngestionRun.id == ingestion_run_id,
            IngestionRun.created_by == user_id,
        )
    )
    return result.scalar_one_or_none()


async def update_ingestion_status(
    db: AsyncSession,
    ingestion_run_id: str,
    status: str,
    *,
    airflow_dag_run_id: str | None = None,
    error_message: str | None = None,
) -> IngestionRun | None:
    run = await get_ingestion_run(db, ingestion_run_id)
    if run is None:
        return None

    now = datetime.now(UTC).replace(tzinfo=None)
    run.status = status
    run.error_message = error_message
    if airflow_dag_run_id is not None:
        run.airflow_dag_run_id = airflow_dag_run_id
    if status == "running" and run.started_at is None:
        run.started_at = now
    if status in TERMINAL_STATUSES:
        run.finished_at = now

    durable_status = DOCUMENT_STATUS_BY_RUN_STATUS[status]
    document = await db.get(Document, run.document_id)
    version = await db.get(DocumentVersion, run.document_version_id)
    if document is not None:
        document.status = durable_status
        if status == "indexed":
            document.current_version_id = run.document_version_id
    if version is not None:
        version.status = durable_status
        version.error_message = error_message
    await db.flush()
    return run


async def mark_ingestion_failed(
    db: AsyncSession,
    ingestion_run_id: str,
    error_message: str,
) -> IngestionRun | None:
    return await update_ingestion_status(
        db,
        ingestion_run_id,
        "failed",
        error_message=error_message,
    )


async def list_failed_runs(db: AsyncSession, project_id: str | None = None) -> list[IngestionRun]:
    statement = select(IngestionRun).where(IngestionRun.status == "failed")
    if project_id is not None:
        statement = statement.where(IngestionRun.project_id == project_id)
    result = await db.execute(statement.order_by(IngestionRun.created_at.desc()))
    return list(result.scalars().all())


async def list_stuck_runs(
    db: AsyncSession,
    older_than: timedelta,
    project_id: str | None = None,
) -> list[IngestionRun]:
    cutoff = datetime.now(UTC).replace(tzinfo=None) - older_than
    statement = select(IngestionRun).where(
        IngestionRun.status.in_(("queued", "running")),
        IngestionRun.created_at < cutoff,
    )
    if project_id is not None:
        statement = statement.where(IngestionRun.project_id == project_id)
    result = await db.execute(statement.order_by(IngestionRun.created_at))
    return list(result.scalars().all())
