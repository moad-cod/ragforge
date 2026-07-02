from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance, Filter, FieldCondition, MatchValue
from app.core.config import settings
import uuid

qdrant = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY or None,
)

def ensure_collection(collection: str, vector_size: int = 384):
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


def index_hierarchical_chunks(
    chunks: list,        # list of HierarchicalChunk dataclasses
    project_id: str,
    document_id: str,
    collection: str,
):
    from app.services.embedder import embed_texts
    ensure_collection(collection)

    texts = [c.text for c in chunks]
    embeddings = embed_texts(texts)

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "text": chunk.text,
                "project_id": project_id,
                "document_id": document_id,
                "chunk_type": chunk.chunk_type,   # "parent" or "child"
                "parent_id": chunk.parent_id,     # None for parents, uuid for children
                "chunk_id": chunk.chunk_id,       # used to look up parent later
                "chunk_index": chunk.index,
            }
        )
        for chunk, embedding in zip(chunks, embeddings)
    ]
    qdrant.upsert(collection_name=collection, points=points)


def delete_document_chunks(document_id: str, collection: str):
    """Delete all points belonging to a document."""
    qdrant.delete(
        collection_name=collection,
        points_selector=Filter(
            must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
        ),
    )

def delete_collection(collection: str):
    """Remove the entire Qdrant collection."""
    existing = [c.name for c in qdrant.get_collections().collections]
    if collection in existing:
        qdrant.delete_collection(collection_name=collection)
def ensure_multimodal_collection(collection: str, vector_size: int = 128):
    """Create a multi-vector collection for ColQwen2 page embeddings."""
    from qdrant_client.models import VectorParams, Distance, MultiVectorConfig, MultiVectorComparator
    existing = [c.name for c in qdrant.get_collections().collections]
    if collection not in existing:
        qdrant.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
                multivector_config=MultiVectorConfig(
                    comparator=MultiVectorComparator.MAX_SIM,
                ),
            ),
        )

def index_multimodal_pages(
    page_embeddings: list[list[list[float]]],
    page_image_urls: list[str],
    project_id: str,
    document_id: str,
    collection: str,
):
    """Store ColQwen2 multi-vector page embeddings in Qdrant."""
    ensure_multimodal_collection(collection)

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=page_emb,          # matrix: (num_patches, 128)
            payload={
                "project_id": project_id,
                "document_id": document_id,
                "page_num": i + 1,
                "page_image_url": url,
                "chunk_type": "page",
            }
        )
        for i, (page_emb, url) in enumerate(zip(page_embeddings, page_image_urls))
    ]
    qdrant.upsert(collection_name=collection, points=points)