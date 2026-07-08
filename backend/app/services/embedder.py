from sentence_transformers import SentenceTransformer

_model = None


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    return _model

def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return get_embedding_model().encode(texts, normalize_embeddings=True).tolist()

def embed_query(query: str) -> list[float]:
    # bge models need this prefix for queries
    return get_embedding_model().encode(f"Represent this sentence: {query}", normalize_embeddings=True).tolist()
