from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk


async def bulk_insert_chunks(db: AsyncSession, chunks: list[Chunk | dict]) -> list[Chunk]:
    records = [chunk if isinstance(chunk, Chunk) else Chunk(**chunk) for chunk in chunks]
    db.add_all(records)
    await db.flush()
    return records


async def replace_chunks_for_document_version(
    db: AsyncSession,
    document_version_id: str,
    chunks: list[Chunk | dict],
) -> list[Chunk]:
    """Replace one version's chunk lineage without committing the transaction.

    Qdrant point and PostgreSQL chunk IDs are deterministic, so a failed or
    repeated indexing job can safely call this operation again.
    """
    await db.execute(delete(Chunk).where(Chunk.document_version_id == document_version_id))
    await db.flush()
    return await bulk_insert_chunks(db, chunks)


async def get_chunks_by_document_version(db: AsyncSession, document_version_id: str) -> list[Chunk]:
    result = await db.execute(
        select(Chunk)
        .where(Chunk.document_version_id == document_version_id)
        .order_by(Chunk.chunk_index)
    )
    return list(result.scalars().all())


async def get_chunk_by_qdrant_point_id(db: AsyncSession, qdrant_point_id: str) -> Chunk | None:
    result = await db.execute(select(Chunk).where(Chunk.qdrant_point_id == qdrant_point_id))
    return result.scalar_one_or_none()


async def delete_chunks_by_document_version(db: AsyncSession, document_version_id: str) -> int:
    result = await db.execute(delete(Chunk).where(Chunk.document_version_id == document_version_id))
    await db.flush()
    return result.rowcount or 0
