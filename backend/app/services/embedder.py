from sentence_transformers import SentenceTransformer

# Downloads once, runs locally — no API key needed
model = SentenceTransformer("BAAI/bge-small-en-v1.5")

def embed_texts(texts: list[str]) -> list[list[float]]:
    return model.encode(texts, normalize_embeddings=True).tolist()

def embed_query(query: str) -> list[float]:
    # bge models need this prefix for queries
    return model.encode(f"Represent this sentence: {query}", normalize_embeddings=True).tolist()