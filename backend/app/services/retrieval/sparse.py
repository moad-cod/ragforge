import hashlib
import re

from fastembed import SparseTextEmbedding
from qdrant_client.models import SparseVector

from app.core.config import settings

_sparse_model = None
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")


def _get_sparse_model() -> SparseTextEmbedding:
    global _sparse_model
    if _sparse_model is None:
        _sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
    return _sparse_model


def _deterministic_sparse(text: str) -> SparseVector:
    values: dict[int, float] = {}
    for token in _TOKEN_PATTERN.findall(text.lower()):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=4).digest()
        index = int.from_bytes(digest, "big")
        values[index] = values.get(index, 0.0) + 1.0
    indices = sorted(values)
    return SparseVector(
        indices=indices,
        values=[values[index] for index in indices],
    )


def embed_sparse(texts: list[str]) -> list[SparseVector]:
    if not texts:
        return []
    if settings.EMBEDDING_BACKEND == "deterministic":
        return [_deterministic_sparse(text) for text in texts]
    if settings.EMBEDDING_BACKEND != "fastembed":
        raise ValueError(f"Unsupported embedding backend {settings.EMBEDDING_BACKEND!r}")
    embeddings = list(_get_sparse_model().embed(texts))
    return [
        SparseVector(indices=e.indices.tolist(), values=e.values.tolist())
        for e in embeddings
    ]


def embed_sparse_query(query: str) -> SparseVector:
    return embed_sparse([query])[0]
