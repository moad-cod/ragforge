_reranker = None
_reranker_unavailable = False


def _get_reranker():
    global _reranker, _reranker_unavailable
    if _reranker_unavailable:
        return None
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            _reranker_unavailable = True
            return None
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker

def rerank(query: str, documents: list[str], top_n: int = 5) -> list[int]:
    """Returns indices of `documents` sorted best-first, truncated to top_n."""
    if not documents:
        return []
    reranker = _get_reranker()
    if reranker is None:
        return list(range(min(top_n, len(documents))))
    pairs = [(query, doc) for doc in documents]
    scores = reranker.predict(pairs)
    ranked_indices = sorted(range(len(documents)), key=lambda i: scores[i], reverse=True)
    return ranked_indices[:top_n]
