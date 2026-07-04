from sentence_transformers import CrossEncoder

# Local cross-encoder — no API key required, consistent with your embedder setup
_reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank(query: str, documents: list[str], top_n: int = 5) -> list[int]:
    """Returns indices of `documents` sorted best-first, truncated to top_n."""
    if not documents:
        return []
    pairs = [(query, doc) for doc in documents]
    scores = _reranker.predict(pairs)
    ranked_indices = sorted(range(len(documents)), key=lambda i: scores[i], reverse=True)
    return ranked_indices[:top_n]