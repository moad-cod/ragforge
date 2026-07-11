from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DocumentVersion


async def create_document_version(db: AsyncSession, **values) -> DocumentVersion:
    version = DocumentVersion(**values)
    db.add(version)
    await db.flush()
    return version


async def get_document_version(db: AsyncSession, document_version_id: str) -> DocumentVersion | None:
    return await db.get(DocumentVersion, document_version_id)


async def get_latest_version_number(db: AsyncSession, document_id: str) -> int:
    result = await db.execute(
        select(func.max(DocumentVersion.version_number)).where(DocumentVersion.document_id == document_id)
    )
    return result.scalar_one_or_none() or 0


async def get_version_by_content_hash(
    db: AsyncSession,
    document_id: str,
    content_hash: str,
) -> DocumentVersion | None:
    result = await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.content_hash == content_hash,
        )
    )
    return result.scalar_one_or_none()


async def list_document_versions(db: AsyncSession, document_id: str) -> list[DocumentVersion]:
    result = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number)
    )
    return list(result.scalars().all())


async def update_version_paths(
    db: AsyncSession,
    document_version_id: str,
    *,
    bronze_path: str | None = None,
    silver_path: str | None = None,
    gold_path: str | None = None,
) -> DocumentVersion | None:
    version = await get_document_version(db, document_version_id)
    if version is not None:
        if bronze_path is not None:
            version.bronze_path = bronze_path
        if silver_path is not None:
            version.silver_path = silver_path
        if gold_path is not None:
            version.gold_path = gold_path
        await db.flush()
    return version


async def update_version_status(
    db: AsyncSession,
    document_version_id: str,
    status: str,
    error_message: str | None = None,
) -> DocumentVersion | None:
    version = await get_document_version(db, document_version_id)
    if version is not None:
        version.status = status
        version.error_message = error_message
        await db.flush()
    return version
