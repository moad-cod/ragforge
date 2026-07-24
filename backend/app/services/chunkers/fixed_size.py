def chunk(
    text: str,
    chunk_size: int = 512,
    overlap: int = 50,
    min_chunk_chars: int = 1,
) -> list[str]:
    """Split text into bounded character windows with optional overlap."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")
    if min_chunk_chars <= 0:
        raise ValueError("min_chunk_chars must be positive")

    text = text.strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0

    while start < len(text):
        proposed_end = min(start + chunk_size, len(text))
        end = proposed_end

        if proposed_end < len(text):
            while end > start and not text[end].isspace():
                end -= 1
            if end == start:
                end = proposed_end

        value = text[start:end].strip()
        if len(value) >= min_chunk_chars:
            chunks.append(value)

        if end >= len(text):
            break

        next_start = end - overlap
        start = next_start if next_start > start else end

    return chunks
