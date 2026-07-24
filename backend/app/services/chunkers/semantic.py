import numpy as np
from app.services.embedder import embed_texts
from app.services.chunkers.tokenize import split_sentences


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a.ndim != 1 or b.ndim != 1 or a.shape != b.shape:
        raise ValueError("embedding vectors must be one-dimensional and equally sized")
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    if denominator == 0:
        return 0.0
    return float(np.dot(a, b) / denominator)


def _merge_short_chunks(chunks: list[str], min_chunk_len: int) -> list[str]:
    if min_chunk_len <= 1:
        return chunks

    merged: list[str] = []
    pending = ""
    for value in chunks:
        candidate = f"{pending} {value}".strip() if pending else value
        if len(candidate) < min_chunk_len:
            pending = candidate
            continue
        merged.append(candidate)
        pending = ""

    if pending:
        if merged:
            merged[-1] = f"{merged[-1]} {pending}".strip()
        else:
            merged.append(pending)
    return merged


def chunk(text: str, threshold: float = 0.5, min_chunk_len: int = 50) -> list[str]:
    """Split text when adjacent sentence embeddings indicate a topic shift."""
    if not -1.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between -1.0 and 1.0")
    if min_chunk_len <= 0:
        raise ValueError("min_chunk_len must be positive")

    sentences = split_sentences(text)
    if not sentences:
        return []
    if len(sentences) == 1:
        return sentences

    embeddings = np.asarray(embed_texts(sentences), dtype=np.float32)
    if embeddings.ndim != 2 or embeddings.shape[0] != len(sentences):
        raise ValueError("embedding backend returned an unexpected number of vectors")

    chunks: list[str] = []
    current = [sentences[0]]

    for i in range(1, len(sentences)):
        sim = _cosine_similarity(embeddings[i - 1], embeddings[i])
        if sim >= threshold:
            current.append(sentences[i])
        else:
            chunks.append(" ".join(current).strip())
            current = [sentences[i]]

    if current:
        chunks.append(" ".join(current).strip())

    return _merge_short_chunks(chunks, min_chunk_len)
