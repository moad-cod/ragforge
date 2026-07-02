from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from app.core.config import settings

qdrant = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY or None,
)

def search(
    embedding: list[float],
    project_id: str,
    collection: str,
    top_k: int = 5,
    document_id: str | None = None,
    use_parent_context: bool = False,
) -> list[str]:

    must_conditions = [
        FieldCondition(key="project_id", match=MatchValue(value=project_id))
    ]
    if document_id:
        must_conditions.append(
            FieldCondition(key="document_id", match=MatchValue(value=document_id))
        )

    # search only child chunks for precision
    if use_parent_context:
        must_conditions.append(
            FieldCondition(key="chunk_type", match=MatchValue(value="child"))
        )

    results = qdrant.query_points(
        collection_name=collection,
        query=embedding,
        query_filter=Filter(must=must_conditions),
        limit=top_k,
    )

    if not use_parent_context:
        return [r.payload["text"] for r in results.points]

    # ── fetch parent chunks for matched children ──────────────────────────────
    contexts = []
    seen_parents = set()

    for r in results.points:
        parent_id = r.payload.get("parent_id")

        if parent_id and parent_id not in seen_parents:
            # ✅ scroll = exact payload filter, no vector needed
            parent_results, _ = qdrant.scroll(
                collection_name=collection,
                scroll_filter=Filter(must=[
                    FieldCondition(key="project_id", match=MatchValue(value=project_id)),
                    FieldCondition(key="chunk_id", match=MatchValue(value=parent_id)),
                ]),
                limit=1,
                with_payload=True,
                with_vectors=False,   # don't need vectors, just text
            )
            if parent_results:
                contexts.append(parent_results[0].payload["text"])
                seen_parents.add(parent_id)
        else:
            # no parent_id means it's not hierarchical — return chunk as-is
            if r.payload.get("parent_id") is None:
                contexts.append(r.payload["text"])

    return contexts