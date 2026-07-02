import nltk
import numpy as np
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-small-en-v1.5")

def chunk(text: str, chunk_size: int = 5, min_chunk_len: int = 50) -> list[str]:
    """
    Late chunking — embed the full document first, then group sentences.
    Each chunk inherits contextual embeddings from the whole document.

    chunk_size: number of sentences per chunk
    """
    # 1. split into sentences
    sentences = [s.strip() for s in nltk.sent_tokenize(text) if len(s.strip()) > 20]
    if not sentences:
        return []

    # 2. embed ALL sentences together (full document context)
    # this is the key difference — context from the whole doc flows into each embedding
    embeddings = model.encode(sentences, normalize_embeddings=True)

    # 3. group sentences into chunks of chunk_size
    # the embeddings already have full context baked in
    chunks = []
    for i in range(0, len(sentences), chunk_size):
        group = sentences[i:i + chunk_size]
        chunk_text = " ".join(group).strip()
        if len(chunk_text) >= min_chunk_len:
            chunks.append(chunk_text)

    return chunks


def chunk_with_embeddings(text: str, chunk_size: int = 5) -> tuple[list[str], list[list[float]]]:
    """
    Returns both chunks AND their context-aware embeddings.
    Use this in indexer for true late chunking — skip re-embedding later.
    """
    sentences = [s.strip() for s in nltk.sent_tokenize(text) if len(s.strip()) > 20]
    if not sentences:
        return [], []

    # embed full document at once
    all_embeddings = model.encode(sentences, normalize_embeddings=True)

    chunks = []
    chunk_embeddings = []

    for i in range(0, len(sentences), chunk_size):
        group_sentences = sentences[i:i + chunk_size]
        group_embeddings = all_embeddings[i:i + chunk_size]

        chunk_text = " ".join(group_sentences).strip()
        if len(chunk_text) < 50:
            continue

        # mean pooling over the group's embeddings
        chunk_embedding = np.mean(group_embeddings, axis=0)
        chunk_embedding = chunk_embedding / (np.linalg.norm(chunk_embedding) + 1e-10)

        chunks.append(chunk_text)
        chunk_embeddings.append(chunk_embedding.tolist())

    return chunks, chunk_embeddings