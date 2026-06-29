from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from app.services.parser import parse_document, parse_url, parse_gdrive
from app.services.embedder import embed_texts
from app.services.indexer import index_chunks
from app.services.chunkers import paragraph, sentence, proposition
import uuid

router = APIRouter()

CHUNKERS = {
    "paragraph": paragraph.chunk,
    "sentence": sentence.chunk,
    "proposition": proposition.chunk,
}

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


# ── Shared indexing logic ─────────────────────────────────────────────────────

def _build_chunks(raw_text: list[str], chunker_name: str) -> list[str]:
    chunker = CHUNKERS.get(chunker_name, paragraph.chunk)
    return chunker("\n\n".join(raw_text))


def _index(chunks: list[str], project_id: str, document_id: str, collection: str):
    embeddings = embed_texts(chunks)   # ← was embed_chunks
    index_chunks(
        chunks=chunks,
        embeddings=embeddings,
        project_id=project_id,
        document_id=document_id,
        collection=collection,
    )


# ── 1. File upload ────────────────────────────────────────────────────────────

@router.post("/file")
async def upload_file(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    collection: str = Form(...),
    chunker: str = Form(default="paragraph"),  # paragraph | sentence | proposition
):
    if file.content_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")

    collection = collection.strip().lower().replace(" ", "_")
    document_id = str(uuid.uuid4())
    file_bytes = await file.read()

    raw_text = parse_document(file_bytes, file.filename)
    chunks = _build_chunks(raw_text, chunker)
    _index(chunks, project_id, document_id, collection)

    return {
        "document_id": document_id,
        "collection": collection,
        "project_id": project_id,
        "filename": file.filename,
        "chunker": chunker,
        "chunks_indexed": len(chunks),
        "sample_chunks": chunks[:3],
    }


# ── 2. URL scrape ─────────────────────────────────────────────────────────────

class URLPayload(BaseModel):
    url: str
    project_id: str
    collection: str
    chunker: str = "paragraph"

@router.post("/url")
async def upload_url(payload: URLPayload):
    collection = payload.collection.strip().lower().replace(" ", "_")
    document_id = str(uuid.uuid4())

    raw_text = await parse_url(payload.url)
    chunks = _build_chunks(raw_text, payload.chunker)
    _index(chunks, payload.project_id, document_id, collection)

    return {
        "document_id": document_id,
        "collection": collection,
        "project_id": payload.project_id,
        "url": payload.url,
        "chunker": payload.chunker,
        "chunks_indexed": len(chunks),
        "sample_chunks": chunks[:3],
    }


# ── 3. Google Drive ───────────────────────────────────────────────────────────

class GDrivePayload(BaseModel):
    file_id: str
    access_token: str
    project_id: str
    collection: str
    chunker: str = "paragraph"

@router.post("/gdrive")
async def upload_gdrive(payload: GDrivePayload):
    collection = payload.collection.strip().lower().replace(" ", "_")
    document_id = str(uuid.uuid4())

    raw_text = await parse_gdrive(payload.file_id, payload.access_token)
    chunks = _build_chunks(raw_text, payload.chunker)
    _index(chunks, payload.project_id, document_id, collection)

    return {
        "document_id": document_id,
        "collection": collection,
        "project_id": payload.project_id,
        "file_id": payload.file_id,
        "chunker": payload.chunker,
        "chunks_indexed": len(chunks),
        "sample_chunks": chunks[:3],
    }