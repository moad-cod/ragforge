from fastembed import SparseTextEmbedding
from qdrant_client.models import SparseVector

# Local BM25 sparse encoder — no API key, same philosophy as embedder.py
_sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")

def embed_sparse(texts: list[str]) -> list[SparseVector]:
    embeddings = list(_sparse_model.embed(texts))
    return [
        SparseVector(indices=e.indices.tolist(), values=e.values.tolist())
        for e in embeddings
    ]

def embed_sparse_query(query: str) -> SparseVector:
    return embed_sparse([query])[0]