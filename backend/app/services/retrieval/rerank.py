from sentence_transformers import CrossEncoder

_reranker = None


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker

def rerank(query: str, documents: list[str], top_n: int = 5) -> list[int]:
    """Returns indices of `documents` sorted best-first, truncated to top_n."""
    if not documents:
        return []
    pairs = [(query, doc) for doc in documents]
    scores = _get_reranker().predict(pairs)
    ranked_indices = sorted(range(len(documents)), key=lambda i: scores[i], reverse=True)
    return ranked_indices[:top_n]
