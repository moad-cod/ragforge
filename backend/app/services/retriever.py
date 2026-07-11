from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from app.core.config import settings
from app.services.retrieval.hybrid import hybrid_search

qdrant = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY or None,
    check_compatibility=False,
)

def search(
    embedding: list[float],
    project_id: str,
    collection: str,
    query_text: str,
    top_k: int = 5,
    document_id: str | None = None,
    use_parent_context: bool = False,
    use_hybrid: bool = True,
) -> list[str]:

    if use_hybrid:
        return hybrid_search(
            dense_embedding=embedding,
            query_text=query_text,
            project_id=project_id,
            collection=collection,
            top_k=top_k,
            document_id=document_id,
            use_parent_context=use_parent_context,
        )

    # dense-only fallback (old behavior)
    must_conditions = [FieldCondition(key="project_id", match=MatchValue(value=project_id))]
    if document_id:
        must_conditions.append(FieldCondition(key="document_id", match=MatchValue(value=document_id)))
    if use_parent_context:
        must_conditions.append(FieldCondition(key="chunk_type", match=MatchValue(value="child")))

    results = qdrant.query_points(
        collection_name=collection,
        query=embedding,
        query_filter=Filter(must=must_conditions),
        limit=top_k,
    )
    return [r.payload["text"] for r in results.points]
