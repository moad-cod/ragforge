"""Normalization and durable retrieval trace helpers for RAG queries."""

import hashlib

from app.services.retrieval.types import RetrievalHit


def normalize_question(question: str) -> str:
    return " ".join(question.casefold().split())


def normalized_question_hash(question: str) -> str:
    normalized = normalize_question(question)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def retrieval_log_values(
    query_log_id: str,
    hits: list[RetrievalHit],
    *,
    from_cache: bool = False,
) -> list[dict]:
    return [
        {
            "query_log_id": query_log_id,
            "chunk_id": hit.chunk_id,
            "qdrant_score": hit.qdrant_score,
            "rerank_score": hit.rerank_score,
            "rank": hit.rank,
            "retrieval_strategy": (
                f"cache:{hit.retrieval_strategy}" if from_cache else hit.retrieval_strategy
            ),
            "used_in_answer": hit.used_in_answer,
        }
        for hit in hits
    ]
