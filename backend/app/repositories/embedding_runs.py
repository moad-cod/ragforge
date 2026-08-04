from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmbeddingRun


async def create_embedding_run(db: AsyncSession, **values) -> EmbeddingRun:
    run = EmbeddingRun(**values)
    db.add(run)
    await db.flush()
    return run


async def get_embedding_run_for_version_model(
    db: AsyncSession,
    document_version_id: str,
    embedding_model: str,
) -> EmbeddingRun | None:
    result = await db.execute(
        select(EmbeddingRun).where(
            EmbeddingRun.document_version_id == document_version_id,
            EmbeddingRun.embedding_model == embedding_model,
        )
    )
    return result.scalar_one_or_none()


async def get_latest_embedding_run(
    db: AsyncSession,
    *,
    project_id: str,
    document_version_id: str,
) -> EmbeddingRun | None:
    result = await db.execute(
        select(EmbeddingRun)
        .where(
            EmbeddingRun.project_id == project_id,
            EmbeddingRun.document_version_id == document_version_id,
        )
        .order_by(EmbeddingRun.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def upsert_embedding_progress(
    db: AsyncSession,
    *,
    project_id: str,
    document_version_id: str,
    embedding_model: str,
    status: str,
    total_chunks: int,
    embedded_chunks: int,
    total_batches: int | None = None,
    embedded_batches: int | None = None,
    batch_size: int | None = None,
    embedding_backend: str | None = None,
    embedding_device: str | None = None,
    embedding_dimension: int | None = None,
    attempt: int | None = None,
    last_heartbeat_at: datetime | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> EmbeddingRun:
    now = datetime.now(UTC).replace(tzinfo=None)
    run = await get_embedding_run_for_version_model(
        db,
        document_version_id,
        embedding_model,
    )
    if run is None:
        run = EmbeddingRun(
            project_id=project_id,
            document_version_id=document_version_id,
            embedding_model=embedding_model,
            status=status,
            total_chunks=total_chunks,
            embedded_chunks=embedded_chunks,
            total_batches=total_batches or 0,
            embedded_batches=embedded_batches or 0,
            batch_size=batch_size,
            embedding_backend=embedding_backend,
            embedding_device=embedding_device,
            embedding_dimension=embedding_dimension,
            attempt=attempt or 1,
            last_heartbeat_at=last_heartbeat_at,
            error_code=error_code,
            error_message=error_message,
        )
        db.add(run)
    else:
        run.status = status
        run.total_chunks = total_chunks
        run.embedded_chunks = embedded_chunks
        if total_batches is not None:
            run.total_batches = total_batches
        if embedded_batches is not None:
            run.embedded_batches = embedded_batches
        if batch_size is not None:
            run.batch_size = batch_size
        if embedding_backend is not None:
            run.embedding_backend = embedding_backend
        if embedding_device is not None:
            run.embedding_device = embedding_device
        if embedding_dimension is not None:
            run.embedding_dimension = embedding_dimension
        if attempt is not None:
            run.attempt = attempt
        if last_heartbeat_at is not None:
            run.last_heartbeat_at = last_heartbeat_at
        run.error_code = error_code
        run.error_message = error_message
    run.updated_at = now
    if status in {"loading_model", "running", "retrying", "completed"}:
        run.started_at = run.started_at or now
    if status in {"completed", "failed", "cancelled"}:
        run.finished_at = now
    else:
        run.finished_at = None
    await db.flush()
    return run


async def update_embedding_progress(
    db: AsyncSession,
    embedding_run_id: str,
    *,
    total_chunks: int | None = None,
    embedded_chunks: int | None = None,
) -> EmbeddingRun | None:
    run = await db.get(EmbeddingRun, embedding_run_id)
    if run is not None:
        if total_chunks is not None:
            run.total_chunks = total_chunks
        if embedded_chunks is not None:
            run.embedded_chunks = embedded_chunks
        if run.status == "queued":
            run.status = "running"
            run.started_at = run.started_at or datetime.now(UTC).replace(tzinfo=None)
        await db.flush()
    return run


async def mark_embedding_completed(db: AsyncSession, embedding_run_id: str) -> EmbeddingRun | None:
    run = await db.get(EmbeddingRun, embedding_run_id)
    if run is not None:
        run.status = "completed"
        run.embedded_chunks = run.total_chunks
        run.finished_at = datetime.now(UTC).replace(tzinfo=None)
        run.error_message = None
        await db.flush()
    return run


async def mark_embedding_failed(
    db: AsyncSession,
    embedding_run_id: str,
    error_message: str,
) -> EmbeddingRun | None:
    run = await db.get(EmbeddingRun, embedding_run_id)
    if run is not None:
        run.status = "failed"
        run.error_message = error_message
        run.finished_at = datetime.now(UTC).replace(tzinfo=None)
        await db.flush()
    return run
