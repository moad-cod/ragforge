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
        end = start + chunk_size

        # avoid cutting in the middle of a word
        if end < len(text):
            # walk back to nearest whitespace
            while end > start and text[end] not in (" ", "\n", "\t"):
                end -= 1
            if end == start:
                end = start + chunk_size  # fallback: hard cut

        value = text[start:end].strip()
        if len(value) >= min_chunk_chars:
            chunks.append(value)

        start = end - overlap  # overlap in characters

    return chunks