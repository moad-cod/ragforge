from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter, FieldCondition, MatchValue, Prefetch, FusionQuery, Fusion
)
from app.core.config import settings
from app.services.retrieval.sparse import embed_sparse_query
from app.services.retrieval.rerank import rerank as rerank_fn

qdrant = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY or None,
)

def _as_text(value) -> str:
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value) if value is not None else ""

def hybrid_search(
    dense_embedding: list[float],
    query_text: str,
    project_id: str,
    collection: str,
    top_k: int = 5,
    fetch_k: int = 30,
    document_id: str | None = None,
    use_parent_context: bool = False,
    use_rerank: bool = True,
) -> list[str]:

    must_conditions = [FieldCondition(key="project_id", match=MatchValue(value=project_id))]
    if document_id:
        must_conditions.append(FieldCondition(key="document_id", match=MatchValue(value=document_id)))
    if use_parent_context:
        must_conditions.append(FieldCondition(key="chunk_type", match=MatchValue(value="child")))

    query_filter = Filter(must=must_conditions)
    sparse_embedding = embed_sparse_query(query_text)

    results = qdrant.query_points(
        collection_name=collection,
        prefetch=[
            Prefetch(query=dense_embedding, using="dense", limit=fetch_k, filter=query_filter),
            Prefetch(query=sparse_embedding, using="sparse", limit=fetch_k, filter=query_filter),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=fetch_k,
        query_filter=query_filter,
    )
    points = results.points
    if not points:
        return []

    if use_rerank:
        candidates = [_as_text(p.payload.get("text")) for p in points]
        best_indices = rerank_fn(query_text, candidates, top_n=top_k)
        points = [points[i] for i in best_indices]
    else:
        points = points[:top_k]

    if not use_parent_context:
        return [_as_text(p.payload.get("text")) for p in points]

    contexts = []
    seen_parents = set()
    for p in points:
        parent_id = p.payload.get("parent_id")
        if parent_id and parent_id not in seen_parents:
            parent_results, _ = qdrant.scroll(
                collection_name=collection,
                scroll_filter=Filter(must=[
                    FieldCondition(key="project_id", match=MatchValue(value=project_id)),
                    FieldCondition(key="chunk_id", match=MatchValue(value=parent_id)),
                ]),
                limit=1,
                with_payload=True,
                with_vectors=False,
            )
            if parent_results:
                contexts.append(_as_text(parent_results[0].payload.get("text")))
                seen_parents.add(parent_id)
        elif p.payload.get("parent_id") is None:
            contexts.append(_as_text(p.payload.get("text")))

    return contexts