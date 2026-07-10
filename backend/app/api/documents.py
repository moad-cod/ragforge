from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.tables import Document, Project
from datetime import datetime
import asyncio

router = APIRouter()


class DocumentResponse(BaseModel):
    document_id: str
    project_id: str
    current_version_id: str | None
    filename: str | None
    source_type: str | None
    mime_type: str | None
    extension: str | None
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime


def _document_payload(document: Document) -> DocumentResponse:
    return DocumentResponse(
        document_id=document.id,
        project_id=document.project_id,
        current_version_id=document.current_version_id,
        filename=document.filename,
        source_type=document.source_type,
        mime_type=document.mime_type,
        extension=document.extension,
        status=document.status,
        created_by=document.created_by,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


# ── helpers ───────────────────────────────────────────────────────────────────

async def _get_project(project_id: str, user_id: str, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.created_by == user_id,
            Project.deleted_at.is_(None),
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(403, "Project not found or access denied")
    return project

async def _get_document(document_id: str, user_id: str, db: AsyncSession) -> Document:
    # join with project to verify ownership
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
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


# ── LIST documents in a project ───────────────────────────────────────────────

@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    await _get_project(project_id, user["user_id"], db)  # verify ownership

    result = await db.execute(
        select(Document).where(
            Document.project_id == project_id,
            Document.deleted_at.is_(None),
        )
    )
    docs = result.scalars().all()
    return [_document_payload(d) for d in docs]


# ── GET single document ───────────────────────────────────────────────────────

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    doc = await _get_document(document_id, user["user_id"], db)
    return _document_payload(doc)


# ── DELETE document ───────────────────────────────────────────────────────────

@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    doc = await _get_document(document_id, user["user_id"], db)

    # delete from Qdrant first
    from app.services.indexer import delete_document_chunks
    project = await _get_project(doc.project_id, user["user_id"], db)
    await asyncio.to_thread(delete_document_chunks, document_id=doc.id, collection=project.collection)

    if doc.source_type == "multimodal":
        from app.services.storage import delete_document_images
        try:
            await asyncio.to_thread(delete_document_images, doc.id)
        except Exception:
            pass

    doc.status = "deleted"
    doc.deleted_at = datetime.utcnow()
    await db.commit()

    return {"deleted": document_id}
