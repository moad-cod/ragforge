import hashlib
import re

import numpy as np
from fastembed import TextEmbedding

from app.core.config import settings

_model = None
_DETERMINISTIC_VECTOR_SIZE = 384
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")


def get_embedding_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _model

def _normalize(vector) -> list[float]:
    arr = np.asarray(vector, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm:
        arr = arr / norm
    return arr.tolist()


def _deterministic_embedding(text: str) -> list[float]:
    """Produce a stable lexical vector for offline integration environments."""
    vector = np.zeros(_DETERMINISTIC_VECTOR_SIZE, dtype=np.float32)
    for token in _TOKEN_PATTERN.findall(text.lower()):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest, "big") % _DETERMINISTIC_VECTOR_SIZE
        vector[index] += 1.0
    return _normalize(vector)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return [_normalize(vector) for vector in get_embedding_model().passage_embed(texts)]

def embed_query(query: str) -> list[float]:
    return _normalize(next(get_embedding_model().query_embed([query])))
