from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, DocumentVersion, IngestionRun


TERMINAL_STATUSES = frozenset({"indexed", "failed", "cancelled"})
ALLOWED_TRANSITIONS = {
    "landed": frozenset({"landed", "queued", "running", "failed", "cancelled"}),
    "queued": frozenset({"queued", "running", "failed", "cancelled"}),
    "running": frozenset({"running", "silver_completed", "failed", "cancelled"}),
    "silver_completed": frozenset({"silver_completed", "gold_completed", "failed", "cancelled"}),
    "gold_completed": frozenset({"gold_completed", "indexed", "failed", "cancelled"}),
    "indexed": frozenset({"indexed"}),
    "failed": frozenset({"failed"}),
    "cancelled": frozenset({"cancelled"}),
}
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


async def list_owned_project_runs(
    db: AsyncSession,
    project_id: str,
    user_id: str,
    *,
    limit: int = 50,
) -> list[IngestionRun]:
    result = await db.execute(
        select(IngestionRun)
        .where(
            IngestionRun.project_id == project_id,
            IngestionRun.created_by == user_id,
        )
        .order_by(IngestionRun.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def retry_failed_ingestion_run(
    db: AsyncSession,
    ingestion_run_id: str,
) -> IngestionRun | None:
    run = await get_ingestion_run(db, ingestion_run_id)
    if run is None:
        return None
    if run.status != "failed":
        raise ValueError("Only failed ingestion runs can be retried")

    run.status = "queued"
    run.started_at = None
    run.finished_at = None
    run.error_message = None
    run.airflow_dag_run_id = None

    document = await db.get(Document, run.document_id)
    version = await db.get(DocumentVersion, run.document_version_id)
    if document is not None:
        document.status = "landed"
    if version is not None:
        version.status = "landed"
        version.error_message = None
        version.silver_path = None
        version.gold_path = None

    await db.flush()
    return run


async def update_ingestion_status(
    db: AsyncSession,
    ingestion_run_id: str,
    status: str,
    *,
    airflow_dag_run_id: str | None = None,
    error_message: str | None = None,
    silver_path: str | None = None,
    gold_path: str | None = None,
) -> IngestionRun | None:
    run = await get_ingestion_run(db, ingestion_run_id)
    if run is None:
        return None
    if status not in ALLOWED_TRANSITIONS.get(run.status, frozenset()):
        raise ValueError(f"Invalid ingestion status transition: {run.status} -> {status}")
    if silver_path is not None and status not in {"silver_completed", "gold_completed", "indexed"}:
        raise ValueError("silver_path can only be recorded after Silver completes")
    if gold_path is not None and status not in {"gold_completed", "indexed"}:
        raise ValueError("gold_path can only be recorded after Gold completes")

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
        if silver_path is not None:
            version.silver_path = silver_path
        if gold_path is not None:
            version.gold_path = gold_path
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
