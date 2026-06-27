from fastapi import APIRouter, UploadFile, File
from app.services.parser import parse_document
from app.services.embedder import embed_texts
from app.services.retriever import store_chunks
import uuid

router = APIRouter()

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    doc_id = str(uuid.uuid4())
    file_bytes = await file.read()

    # 1. Parse
    chunks = parse_document(file_bytes, file.filename)

    # 2. Embed
    embeddings = embed_texts(chunks)

    # 3. Store in Qdrant
    store_chunks(chunks, embeddings, doc_id)

    return {
        "doc_id": doc_id,
        "filename": file.filename,
        "chunks_indexed": len(chunks),
    }