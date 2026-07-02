def chunk(text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
    """
    Split text into fixed-size chunks by character count with overlap.
    Unlike paragraph.py (word-based), this splits on characters — 
    more predictable token counts for LLM context windows.
    """
    if not text.strip():
        return []

    chunks = []
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

        chunk = text[start:end].strip()
        if len(chunk) > 30:
            chunks.append(chunk)

        start = end - overlap  # overlap in characters

    return chunks