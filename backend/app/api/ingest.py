from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.tables import Project, Document
from app.services.parser import parse_document, parse_url, parse_gdrive
from app.services.embedder import embed_texts
from app.services.indexer import index_chunks, index_hierarchical_chunks, index_multimodal_pages
from app.services.chunkers.registry import ChunkerType, get_chunker
from app.services.chunkers import late_chunking as late_chunking_module
from app.services.chunkers import hierarchical as hierarchical_module
from app.services.chunkers.multimodal import ingest_pdf_multimodal
from app.core.config import settings
from app.services.storage import delete_document_images
import asyncio
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

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx", ".csv", ".html", ".htm", ".md", ".txt"}


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
    if not chunks:
        raise HTTPException(400, "No indexable text was extracted from the document")
    embeddings = embed_texts(chunks)
    index_chunks(
        chunks=chunks,
        embeddings=embeddings,
        project_id=project_id,
        document_id=document_id,
        collection=collection,
    )

def _index_late_chunking(text: str, project_id: str, document_id: str, collection: str) -> list[str]:
    chunks, embeddings = late_chunking_module.chunk_with_embeddings(text)
    index_chunks(
        chunks=chunks,
        embeddings=embeddings,
        project_id=project_id,
        document_id=document_id,
        collection=collection,
    )
    return chunks

def _index_hierarchical(text: str, project_id: str, document_id: str, collection: str) -> list[str]:
    chunks = hierarchical_module.chunk_hierarchical(text)
    index_hierarchical_chunks(chunks, project_id, document_id, collection)
    return [c.text for c in chunks if c.chunk_type == "child"]

def _process_and_index(
    raw_text: list[str],
    chunker: ChunkerType,
    project_id: str,
    document_id: str,
    collection: str,
) -> list[str]:
    """Single entry point for all chunking strategies."""
    full_text = "\n\n".join(raw_text)
    if chunker == ChunkerType.late_chunking:
        return _index_late_chunking(full_text, project_id, document_id, collection)
    elif chunker == ChunkerType.hierarchical:
        return _index_hierarchical(full_text, project_id, document_id, collection)
    else:
        chunks = _build_chunks(raw_text, chunker)
        _index(chunks, project_id, document_id, collection)
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

def _extension(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()

async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File is too large. Max size is {settings.MAX_UPLOAD_BYTES} bytes")
    return data

def _validate_file(file: UploadFile):
    ext = _extension(file.filename)
    if ext not in SUPPORTED_EXTENSIONS and file.content_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(400, f"Unsupported file type: {file.content_type or ext or 'unknown'}")

def _ingest_text_document(
    file_bytes: bytes,
    filename: str,
    chunker: ChunkerType,
    project_id: str,
    document_id: str,
    collection: str,
) -> list[str]:
    raw_text = parse_document(file_bytes, filename)
    return _process_and_index(raw_text, chunker, project_id, document_id, collection)

async def _cleanup_document_artifacts(document_id: str, collection: str, source: str):
    from app.services.indexer import delete_document_chunks
    try:
        await asyncio.to_thread(delete_document_chunks, document_id=document_id, collection=collection)
    except Exception:
        pass
    if source == "multimodal":
        try:
            await asyncio.to_thread(delete_document_images, document_id)
        except Exception:
            pass

def _debug_payload(chunks: list[str]) -> dict:
    if not settings.DEBUG_RETURN_CONTEXT:
        return {}
    return {"sample_chunks": chunks[:3]}


# ── 1. File upload ────────────────────────────────────────────────────────────
@router.post("/multimodal")
async def upload_multimodal(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if file.content_type != "application/pdf":
        raise HTTPException(400, "Multimodal ingestion only supports PDF files")
    try:
        settings.require_r2()
    except ValueError as exc:
        raise HTTPException(503, str(exc))

    project = await _get_project(project_id, user["user_id"], db)
    document_id = str(uuid.uuid4())
    file_bytes = await _read_upload(file)

    try:
        page_embeddings, page_image_urls, num_pages = await asyncio.to_thread(
            ingest_pdf_multimodal, file_bytes, document_id, settings.MAX_MULTIMODAL_PAGES
        )

        collection = f"{project.collection}_multimodal"
        await asyncio.to_thread(
            index_multimodal_pages,
            page_embeddings=page_embeddings,
            page_image_urls=page_image_urls,
            project_id=project_id,
            document_id=document_id,
            collection=collection,
        )

        await _save_document(
            db, document_id, project_id,
            collection, file.filename, "multimodal", num_pages
        )
    except ValueError as exc:
        await _cleanup_document_artifacts(document_id, f"{project.collection}_multimodal", "multimodal")
        raise HTTPException(413, str(exc))
    except Exception:
        await _cleanup_document_artifacts(document_id, f"{project.collection}_multimodal", "multimodal")
        raise

    return {
        "document_id": document_id,
        "project_id": project_id,
        "collection": collection,
        "filename": file.filename,
        "pages_indexed": num_pages,
        "page_image_urls": page_image_urls,
    }
@router.post("/file")
async def upload_file(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    chunker: ChunkerType = Form(default=ChunkerType.paragraph),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    project = await _get_project(project_id, user["user_id"], db)
    _validate_file(file)

    document_id = str(uuid.uuid4())
    file_bytes = await _read_upload(file)

    try:
        chunks = await asyncio.to_thread(
            _ingest_text_document,
            file_bytes,
            file.filename,
            chunker,
            project_id,
            document_id,
            project.collection,
        )
        await _save_document(
            db, document_id, project_id,
            project.collection, file.filename, "file", len(chunks)
        )
    except Exception:
        await _cleanup_document_artifacts(document_id, project.collection, "file")
        raise

    return {
        "document_id": document_id,
        "project_id": project_id,
        "collection": project.collection,
        "filename": file.filename,
        "chunker": chunker.value,
        "chunks_indexed": len(chunks),
        **_debug_payload(chunks),
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

    try:
        chunks = await asyncio.to_thread(
            _process_and_index,
            raw_text,
            payload.chunker,
            payload.project_id,
            document_id,
            project.collection,
        )
        await _save_document(
            db, document_id, payload.project_id,
            project.collection, payload.url, "url", len(chunks)
        )
    except Exception:
        await _cleanup_document_artifacts(document_id, project.collection, "url")
        raise

    return {
        "document_id": document_id,
        "project_id": payload.project_id,
        "collection": project.collection,
        "url": payload.url,
        "chunker": payload.chunker.value,
        "chunks_indexed": len(chunks),
        **_debug_payload(chunks),
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

    try:
        chunks = await asyncio.to_thread(
            _process_and_index,
            raw_text,
            payload.chunker,
            payload.project_id,
            document_id,
            project.collection,
        )
        await _save_document(
            db, document_id, payload.project_id,
            project.collection, payload.file_id, "gdrive", len(chunks)
        )
    except Exception:
        await _cleanup_document_artifacts(document_id, project.collection, "gdrive")
        raise

    return {
        "document_id": document_id,
        "project_id": payload.project_id,
        "collection": project.collection,
        "file_id": payload.file_id,
        "chunker": payload.chunker.value,
        "chunks_indexed": len(chunks),
        **_debug_payload(chunks),
    }
