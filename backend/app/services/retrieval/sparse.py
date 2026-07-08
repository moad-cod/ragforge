from fastembed import SparseTextEmbedding
from qdrant_client.models import SparseVector

_sparse_model = None


def _get_sparse_model() -> SparseTextEmbedding:
    global _sparse_model
    if _sparse_model is None:
        _sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
    return _sparse_model

def embed_sparse(texts: list[str]) -> list[SparseVector]:
    if not texts:
        return []
    embeddings = list(_get_sparse_model().embed(texts))
    return [
        SparseVector(indices=e.indices.tolist(), values=e.values.tolist())
        for e in embeddings
    ]

def embed_sparse_query(query: str) -> SparseVector:
    return embed_sparse([query])[0]
