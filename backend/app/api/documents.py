from fastapi import APIRouter, UploadFile, File, Query
from app.services.parser import parse_document
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

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    version: str = Query(default="v1", enum=["v1", "v2", "v3"]),
):
    doc_id = str(uuid.uuid4())
    file_bytes = await file.read()

    # 1. Parse PDF → raw text
    raw_text = parse_document(file_bytes, file.filename)

    # 2. Chunk based on version
    chunker = CHUNKERS[version]
    chunks = chunker("\n\n".join(raw_text))

    # 3. Embed
    embeddings = embed_texts(chunks)

    # 4. Store in Qdrant — use different collection per version
    store_chunks(chunks, embeddings, doc_id, collection=f"ragforge_{version}")

    return {
        "doc_id": doc_id,
        "version": version,
        "filename": file.filename,
        "chunks_indexed": len(chunks),
        "sample_chunks": chunks[:3],   # preview first 3 chunks
    }