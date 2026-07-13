"""Shared retrieval result types used by querying and observability."""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class RetrievalHit:
    text: str
    chunk_id: str | None
    qdrant_point_id: str | None
    qdrant_score: float | None
    rerank_score: float | None
    rank: int
    retrieval_strategy: str
    used_in_answer: bool = False
    payload: dict[str, Any] | None = None

    def to_cache_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("payload", None)
        return value

    @classmethod
    def from_cache_dict(cls, value: dict[str, Any]) -> "RetrievalHit":
        return cls(**value)
