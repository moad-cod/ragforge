import numpy as np
from fastembed import TextEmbedding

_model = None


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

def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return [_normalize(vector) for vector in get_embedding_model().passage_embed(texts)]

def embed_query(query: str) -> list[float]:
    return _normalize(next(get_embedding_model().query_embed([query])))
