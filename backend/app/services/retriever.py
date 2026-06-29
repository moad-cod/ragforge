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
) -> list[str]:

    must_conditions = [
        FieldCondition(key="project_id", match=MatchValue(value=project_id))
    ]

    if document_id:
        must_conditions.append(
            FieldCondition(key="document_id", match=MatchValue(value=document_id))
        )

    results = qdrant.query_points(
        collection_name=collection,
        query=embedding,
        query_filter=Filter(must=must_conditions),
        limit=top_k,
    )

    return [r.payload["text"] for r in results.points]
#                                              ↑ .points — result is wrapped