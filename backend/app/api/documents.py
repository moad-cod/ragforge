from fastapi import APIRouter, UploadFile, File, Query, HTTPException
from pydantic import BaseModel
from app.services.parser import parse_document, parse_url, parse_gdrive
from app.services.embedder import embed_texts
from app.services.retriever import store_chunks
from app.services.chunkers import paragraph, sentence, proposition
import uuid

router = APIRouter()

CHUNKERS = {
    "v1": paragraph.chunk,
    "v2": proposition.chunk,
    "v3": sentence.chunk,
}

SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",        # .xlsx
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",# .pptx
    "text/csv",
    "text/html",
    "text/plain",
    "text/markdown",
}
# ── 1. File upload (PDF, DOCX, TXT, MD) ─────────────────────────────────────

@router.post("/upload/file")
async def upload_file(
    file: UploadFile = File(...),
    version: str = Query(default="v1", enum=["v1", "v2", "v3"]),
):
    if file.content_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")

    doc_id = str(uuid.uuid4())
    file_bytes = await file.read()
    raw_text = parse_document(file_bytes, file.filename)

    return await _index(raw_text, doc_id, version, source="file", name=file.filename)


# ── 2. Raw URL scrape (public web pages, sitemaps) ───────────────────────────

class URLPayload(BaseModel):
    url: str
    version: str = "v1"

@router.post("/upload/url")
async def upload_url(payload: URLPayload):
    doc_id = str(uuid.uuid4())
    raw_text = await parse_url(payload.url)   # fetch + strip HTML
    return await _index(raw_text, doc_id, payload.version, source="url", name=payload.url)


# ── 3. Google Drive (OAuth token passed by frontend after user connects) ──────

class GDrivePayload(BaseModel):
    file_id: str
    access_token: str
    version: str = "v1"

@router.post("/upload/gdrive")
async def upload_gdrive(payload: GDrivePayload):
    doc_id = str(uuid.uuid4())
    raw_text = await parse_gdrive(payload.file_id, payload.access_token)
    return await _index(raw_text, doc_id, payload.version, source="gdrive", name=payload.file_id)


# ── Shared indexing logic ────────────────────────────────────────────────────

async def _index(raw_text: list[str], doc_id: str, version: str, source: str, name: str):
    chunker = CHUNKERS[version]
    chunks = chunker("\n\n".join(raw_text))
    embeddings = embed_texts(chunks)
    store_chunks(chunks, embeddings, doc_id, collection=f"ragforge_{version}")

    return {
        "doc_id": doc_id,
        "version": version,
        "source": source,
        "name": name,
        "chunks_indexed": len(chunks),
        "sample_chunks": chunks[:3],
    }