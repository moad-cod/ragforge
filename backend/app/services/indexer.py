from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from app.core.config import settings
import uuid

qdrant = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY or None,  
)

def ensure_collection(collection: str, vector_size: int = 384):
    """Create collection if it doesn't exist yet."""
    existing = [c.name for c in qdrant.get_collections().collections]
    if collection not in existing:
        qdrant.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

def index_chunks(
    chunks: list[str],
    embeddings: list[list[float]],
    project_id: str,
    document_id: str,
    collection: str,          
):
    ensure_collection(collection)

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "text": chunk,
                "project_id": project_id,
                "document_id": document_id,
                "chunk_index": i,
            }
        )
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]
    qdrant.upsert(collection_name=collection, points=points)