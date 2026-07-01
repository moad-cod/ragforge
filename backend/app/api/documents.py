from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.tables import Document, Project

router = APIRouter()


# ── helpers ───────────────────────────────────────────────────────────────────

async def _get_project(project_id: str, user_id: str, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
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
        .where(Document.id == document_id, Project.user_id == user_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


# ── LIST documents in a project ───────────────────────────────────────────────

@router.get("/")
async def list_documents(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    await _get_project(project_id, user["user_id"], db)  # verify ownership

    result = await db.execute(
        select(Document).where(Document.project_id == project_id)
    )
    docs = result.scalars().all()
    return [
        {
            "document_id": d.id,
            "project_id": d.project_id,
            "filename": d.filename,
            "source": d.source,
            "chunks": d.chunks,
            "created_at": d.created_at,
        }
        for d in docs
    ]


# ── GET single document ───────────────────────────────────────────────────────

@router.get("/{document_id}")
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    doc = await _get_document(document_id, user["user_id"], db)
    return {
        "document_id": doc.id,
        "project_id": doc.project_id,
        "filename": doc.filename,
        "source": doc.source,
        "chunks": doc.chunks,
        "created_at": doc.created_at,
    }


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
    delete_document_chunks(document_id=doc.id, collection=doc.collection)

    # delete from postgres
    await db.delete(doc)
    await db.commit()

    return {"deleted": document_id}