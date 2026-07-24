from app.services.chunkers.tokenize import split_sentences


def chunk(text: str, min_chunk_chars: int = 30) -> list[str]:
    """Return sentence-aligned chunks without dropping short text fragments."""
    if min_chunk_chars <= 0:
        raise ValueError("min_chunk_chars must be positive")

    sentences = split_sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    pending: list[str] = []

    for sentence in sentences:
        pending.append(sentence)
        candidate = " ".join(pending).strip()
        if len(candidate) >= min_chunk_chars:
            chunks.append(candidate)
            pending = []

    if pending:
        tail = " ".join(pending).strip()
        if chunks:
            chunks[-1] = f"{chunks[-1]} {tail}".strip()
        elif tail:
            chunks.append(tail)

    return chunks
