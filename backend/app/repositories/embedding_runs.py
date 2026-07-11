from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmbeddingRun


async def create_embedding_run(db: AsyncSession, **values) -> EmbeddingRun:
    run = EmbeddingRun(**values)
    db.add(run)
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
