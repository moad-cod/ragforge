from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from app.core.config import settings
import uuid

client = QdrantClient(url=settings.QDRANT_URL)
COLLECTION = settings.QDRANT_COLLECTION
VECTOR_SIZE = 384

def ensure_collection():
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

def store_chunks(chunks: list[str], embeddings: list[list[float]], doc_id: str):
    ensure_collection()
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=emb,
            payload={"text": chunk, "doc_id": doc_id},
        )
        for chunk, emb in zip(chunks, embeddings)
    ]
    client.upsert(collection_name=COLLECTION, points=points)

def search(query_embedding: list[float], top_k: int = 5) -> list[str]:
    # Modern Qdrant API
    results = client.query_points(
        collection_name=COLLECTION,
        query=query_embedding,  # renamed from query_vector -> query
        limit=top_k,            # renamed from top_k -> limit
    ).points                     # .query_points returns an object with a .points list
    
    return [r.payload["text"] for r in results if r.payload and "text" in r.payload]