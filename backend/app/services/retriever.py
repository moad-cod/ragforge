from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from app.core.config import settings
import uuid

client = QdrantClient(url=settings.QDRANT_URL)
VECTOR_SIZE = 384

def ensure_collection(collection: str):
    existing = [c.name for c in client.get_collections().collections]
    if collection not in existing:
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

def store_chunks(chunks, embeddings, doc_id, collection=settings.QDRANT_COLLECTION):
    ensure_collection(collection)
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=emb,
            payload={"text": chunk, "doc_id": doc_id},
        )
        for chunk, emb in zip(chunks, embeddings)
    ]
    client.upsert(collection_name=collection, points=points)

def search(query_embedding: list[float], top_k: int = 5, collection: str = None) -> list[str]:
    # Use the dynamic collection passed in, or fall back to your default constant
    target_collection = collection if collection else COLLECTION
    
    # Modern Qdrant API method
    results = client.query_points(
        collection_name=target_collection,
        query=query_embedding,
        limit=top_k,
    ).points
    
    return [r.payload["text"] for r in results if r.payload and "text" in r.payload]