from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.tables import Project, Document
from app.services.parser import parse_document, parse_url, parse_gdrive
from app.services.embedder import embed_texts
from app.services.indexer import index_chunks
from app.services.chunkers.registry import ChunkerType, get_chunker
from app.services.chunkers import late_chunking as late_chunking_module
import uuid

router = APIRouter()

SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/csv",
    "text/html",
    "text/plain",
    "text/markdown",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_project(project_id: str, user_id: str, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(403, "Project not found or access denied")
    return project

def _build_chunks(raw_text: list[str], chunker_type: ChunkerType) -> list[str]:
    chunker = get_chunker(chunker_type)
    return chunker("\n\n".join(raw_text))

def _index(chunks: list[str], project_id: str, document_id: str, collection: str):
    embeddings = embed_texts(chunks)
    index_chunks(
        chunks=chunks,
        embeddings=embeddings,
        project_id=project_id,
        document_id=document_id,
        collection=collection,
    )

def _index_late_chunking(text: str, project_id: str, document_id: str, collection: str) -> list[str]:
    """Special path — embeddings come from the chunker itself, skip re-embedding."""
    chunks, embeddings = late_chunking_module.chunk_with_embeddings(text)
    index_chunks(
        chunks=chunks,
        embeddings=embeddings,
        project_id=project_id,
        document_id=document_id,
        collection=collection,
    )
    return chunks

async def _save_document(
    db: AsyncSession,
    document_id: str,
    project_id: str,
    collection: str,
    filename: str,
    source: str,
    chunks_count: int,
):
    doc = Document(
        id=document_id,
        project_id=project_id,
        collection=collection,
        filename=filename,
        source=source,
        chunks=str(chunks_count),
    )
    db.add(doc)
    await db.commit()


# ── 1. File upload ────────────────────────────────────────────────────────────

@router.post("/file")
async def upload_file(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    chunker: ChunkerType = Form(default=ChunkerType.paragraph),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    project = await _get_project(project_id, user["user_id"], db)

    if file.content_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")

    document_id = str(uuid.uuid4())
    file_bytes = await file.read()
    raw_text = parse_document(file_bytes, file.filename)
    full_text = "\n\n".join(raw_text)

    # ← late chunking uses its own embeddings
    if chunker == ChunkerType.late_chunking:
        chunks = _index_late_chunking(full_text, project_id, document_id, project.collection)
    else:
        chunks = _build_chunks(raw_text, chunker)
        _index(chunks, project_id, document_id, project.collection)

    await _save_document(
        db, document_id, project_id,
        project.collection, file.filename, "file", len(chunks)
    )

    return {
        "document_id": document_id,
        "project_id": project_id,
        "collection": project.collection,
        "filename": file.filename,
        "chunker": chunker.value,
        "chunks_indexed": len(chunks),
        "sample_chunks": chunks[:3],
    }


# ── 2. URL scrape ─────────────────────────────────────────────────────────────

class URLPayload(BaseModel):
    url: str
    project_id: str
    chunker: ChunkerType = ChunkerType.paragraph

@router.post("/url")
async def upload_url(
    payload: URLPayload,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    project = await _get_project(payload.project_id, user["user_id"], db)
    document_id = str(uuid.uuid4())
    raw_text = await parse_url(payload.url)
    full_text = "\n\n".join(raw_text)

    if payload.chunker == ChunkerType.late_chunking:
        chunks = _index_late_chunking(full_text, payload.project_id, document_id, project.collection)
    else:
        chunks = _build_chunks(raw_text, payload.chunker)
        _index(chunks, payload.project_id, document_id, project.collection)

    await _save_document(
        db, document_id, payload.project_id,
        project.collection, payload.url, "url", len(chunks)
    )

    return {
        "document_id": document_id,
        "project_id": payload.project_id,
        "collection": project.collection,
        "url": payload.url,
        "chunker": payload.chunker.value,
        "chunks_indexed": len(chunks),
        "sample_chunks": chunks[:3],
    }


# ── 3. Google Drive ───────────────────────────────────────────────────────────

class GDrivePayload(BaseModel):
    file_id: str
    access_token: str
    project_id: str
    chunker: ChunkerType = ChunkerType.paragraph

@router.post("/gdrive")
async def upload_gdrive(
    payload: GDrivePayload,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    project = await _get_project(payload.project_id, user["user_id"], db)
    document_id = str(uuid.uuid4())
    raw_text = await parse_gdrive(payload.file_id, payload.access_token)
    full_text = "\n\n".join(raw_text)

    if payload.chunker == ChunkerType.late_chunking:
        chunks = _index_late_chunking(full_text, payload.project_id, document_id, project.collection)
    else:
        chunks = _build_chunks(raw_text, payload.chunker)
        _index(chunks, payload.project_id, document_id, project.collection)

    await _save_document(
        db, document_id, payload.project_id,
        project.collection, payload.file_id, "gdrive", len(chunks)
    )

    return {
        "document_id": document_id,
        "project_id": payload.project_id,
        "collection": project.collection,
        "file_id": payload.file_id,
        "chunker": payload.chunker.value,
        "chunks_indexed": len(chunks),
        "sample_chunks": chunks[:3],
    }