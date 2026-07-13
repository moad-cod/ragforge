from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter, FieldCondition, MatchValue, Prefetch, FusionQuery, Fusion
)
from app.core.config import settings
from app.services.retrieval.sparse import embed_sparse_query
from app.services.retrieval.rerank import rerank_with_scores
from app.services.retrieval.types import RetrievalHit

qdrant = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY or None,
    check_compatibility=False,
)

def _as_text(value) -> str:
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value) if value is not None else ""


def _lineage_chunk_id(payload: dict) -> str | None:
    """Only trust PostgreSQL chunk IDs from control-plane indexed payloads."""
    if payload.get("document_version_id") and payload.get("chunk_id"):
        return str(payload["chunk_id"])
    return None


def _point_hit(point, *, strategy: str) -> RetrievalHit:
    payload = dict(point.payload or {})
    return RetrievalHit(
        text=_as_text(payload.get("text")),
        chunk_id=_lineage_chunk_id(payload),
        qdrant_point_id=str(point.id) if point.id is not None else None,
        qdrant_score=float(point.score) if point.score is not None else None,
        rerank_score=None,
        rank=0,
        retrieval_strategy=strategy,
        payload=payload,
    )

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
) -> list[RetrievalHit]:

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
    if not results.points:
        return []

    hits = [_point_hit(point, strategy="hybrid_rrf") for point in results.points]

    if use_rerank:
        ranked = rerank_with_scores(query_text, [hit.text for hit in hits], top_n=top_k)
        hits = [hits[index] for index, _score in ranked]
        for hit, (_index, score) in zip(hits, ranked):
            hit.rerank_score = score
            if score is not None:
                hit.retrieval_strategy = "hybrid_rrf_cross_encoder"
    else:
        hits = hits[:top_k]

    if not use_parent_context:
        for rank, hit in enumerate(hits, start=1):
            hit.rank = rank
        return hits

    contexts: list[RetrievalHit] = []
    seen_parents = set()
    for hit in hits:
        payload = hit.payload or {}
        parent_id = payload.get("parent_id")
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
                hit.text = _as_text(parent_results[0].payload.get("text"))
                hit.retrieval_strategy = f"{hit.retrieval_strategy}_parent_context"
                contexts.append(hit)
                seen_parents.add(parent_id)
        elif payload.get("parent_id") is None:
            contexts.append(hit)

    for rank, hit in enumerate(contexts, start=1):
        hit.rank = rank
    return contexts
