import numpy as np

from app.services.embedder import embed_texts
from app.services.chunkers.tokenize import split_sentences


def _sentence_groups(
    text: str,
    chunk_size: int,
    min_chunk_len: int,
) -> list[list[str]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if min_chunk_len <= 0:
        raise ValueError("min_chunk_len must be positive")

    sentences = split_sentences(text)
    if not sentences:
        return []

    raw_groups = [
        sentences[start:start + chunk_size]
        for start in range(0, len(sentences), chunk_size)
    ]
    groups: list[list[str]] = []
    pending: list[str] = []
    for group in raw_groups:
        candidate = pending + group
        if len(" ".join(candidate).strip()) < min_chunk_len:
            pending = candidate
            continue
        groups.append(candidate)
        pending = []

    if pending:
        if groups:
            groups[-1].extend(pending)
        else:
            groups.append(pending)
    return groups


def chunk(text: str, chunk_size: int = 5, min_chunk_len: int = 50) -> list[str]:
    """Group sentences for callers that need text chunks only."""
    return [
        " ".join(group).strip()
        for group in _sentence_groups(text, chunk_size, min_chunk_len)
    ]


def chunk_with_embeddings(
    text: str,
    chunk_size: int = 5,
    min_chunk_len: int = 50,
) -> tuple[list[str], list[list[float]]]:
    """Return sentence groups and normalized mean-pooled sentence vectors."""
    groups = _sentence_groups(text, chunk_size, min_chunk_len)
    if not groups:
        return [], []

    sentences = [sentence for group in groups for sentence in group]
    all_embeddings = np.asarray(embed_texts(sentences), dtype=np.float32)
    if all_embeddings.ndim != 2 or all_embeddings.shape[0] != len(sentences):
        raise ValueError("embedding backend returned an unexpected number of vectors")

    chunks: list[str] = []
    chunk_embeddings: list[list[float]] = []
    offset = 0

    for group in groups:
        group_embeddings = all_embeddings[offset:offset + len(group)]
        offset += len(group)
        # mean pooling over the group's embeddings
        chunk_embedding = np.mean(group_embeddings, axis=0)
        norm = np.linalg.norm(chunk_embedding)
        if norm:
            chunk_embedding = chunk_embedding / norm

        chunks.append(" ".join(group).strip())
        chunk_embeddings.append(chunk_embedding.tolist())

    return chunks, chunk_embeddings
