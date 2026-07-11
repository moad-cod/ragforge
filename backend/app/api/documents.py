from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.tables import Document, DocumentVersion, Project
from app.repositories import document_versions as version_repository
from app.repositories import documents as document_repository
from app.repositories import projects as project_repository
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


class DocumentVersionResponse(BaseModel):
    document_version_id: str
    document_id: str
    version_number: int
    content_hash: str
    bronze_path: str | None
    silver_path: str | None
    gold_path: str | None
    parser_name: str | None
    chunker_id: str | None
    embedding_model: str | None
    status: str
    error_message: str | None
    created_at: datetime


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


def _document_version_payload(version: DocumentVersion) -> DocumentVersionResponse:
    return DocumentVersionResponse(
        document_version_id=version.id,
        document_id=version.document_id,
        version_number=version.version_number,
        content_hash=version.content_hash,
        bronze_path=version.bronze_path,
        silver_path=version.silver_path,
        gold_path=version.gold_path,
        parser_name=version.parser_name,
        chunker_id=version.chunker_id,
        embedding_model=version.embedding_model,
        status=version.status,
        error_message=version.error_message,
        created_at=version.created_at,
    )


# ── helpers ───────────────────────────────────────────────────────────────────

async def _get_project(project_id: str, user_id: str, db: AsyncSession) -> Project:
    project = await project_repository.get_owned_project(db, project_id, user_id)
    if not project:
        raise HTTPException(403, "Project not found or access denied")
    return project

async def _get_document(document_id: str, user_id: str, db: AsyncSession) -> Document:
    doc = await document_repository.get_owned_document(db, document_id, user_id)
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

    docs = await document_repository.list_project_documents(db, project_id)
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


@router.get("/{document_id}/versions", response_model=list[DocumentVersionResponse])
async def list_document_versions(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    doc = await _get_document(document_id, user["user_id"], db)
    versions = await version_repository.list_document_versions(db, doc.id)
    return [_document_version_payload(version) for version in versions]


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

    await document_repository.soft_delete_document(db, doc.id)
    await db.commit()

    return {"deleted": document_id}
