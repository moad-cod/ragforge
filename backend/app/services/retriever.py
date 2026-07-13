from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from app.core.config import settings
from app.services.retrieval.hybrid import hybrid_search
from app.services.retrieval.types import RetrievalHit

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
) -> list[RetrievalHit]:

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
    hits = []
    for rank, point in enumerate(results.points, start=1):
        payload = dict(point.payload or {})
        hits.append(
            RetrievalHit(
                text=str(payload.get("text") or ""),
                chunk_id=(
                    str(payload["chunk_id"])
                    if payload.get("document_version_id") and payload.get("chunk_id")
                    else None
                ),
                qdrant_point_id=str(point.id) if point.id is not None else None,
                qdrant_score=float(point.score) if point.score is not None else None,
                rerank_score=None,
                rank=rank,
                retrieval_strategy="dense",
                payload=payload,
            )
        )
    return hits
