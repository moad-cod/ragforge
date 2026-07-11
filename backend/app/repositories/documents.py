from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, Project


async def create_document(db: AsyncSession, **values) -> Document:
    document = Document(**values)
    db.add(document)
    await db.flush()
    return document


async def get_document(
    db: AsyncSession,
    document_id: str,
    *,
    include_deleted: bool = False,
) -> Document | None:
    statement = select(Document).where(Document.id == document_id)
    if not include_deleted:
        statement = statement.where(Document.deleted_at.is_(None))
    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def get_owned_document(db: AsyncSession, document_id: str, user_id: str) -> Document | None:
    result = await db.execute(
        select(Document)
        .join(Project, Document.project_id == Project.id)
        .where(
            Document.id == document_id,
            Document.deleted_at.is_(None),
            Project.created_by == user_id,
            Project.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def find_logical_document(
    db: AsyncSession,
    project_id: str,
    filename: str,
    source_type: str,
) -> Document | None:
    result = await db.execute(
        select(Document).where(
            Document.project_id == project_id,
            Document.filename == filename,
            Document.source_type == source_type,
            Document.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def list_project_documents(db: AsyncSession, project_id: str) -> list[Document]:
    result = await db.execute(
        select(Document)
        .where(Document.project_id == project_id, Document.deleted_at.is_(None))
        .order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


async def update_document_status(db: AsyncSession, document_id: str, status: str) -> Document | None:
    document = await get_document(db, document_id, include_deleted=True)
    if document is not None:
        document.status = status
        await db.flush()
    return document


async def set_current_version(
    db: AsyncSession,
    document_id: str,
    document_version_id: str,
) -> Document | None:
    document = await get_document(db, document_id)
    if document is not None:
        document.current_version_id = document_version_id
        await db.flush()
    return document


async def soft_delete_document(db: AsyncSession, document_id: str) -> Document | None:
    document = await get_document(db, document_id)
    if document is not None:
        document.status = "deleted"
        document.deleted_at = datetime.now(UTC).replace(tzinfo=None)
        await db.flush()
    return document
