import re


_PARAGRAPH_BREAK = re.compile(r"\n\s*\n+")


def _word_windows(words: list[str], chunk_size: int, overlap: int) -> list[str]:
    windows: list[str] = []
    step = chunk_size - overlap
    for start in range(0, len(words), step):
        value = " ".join(words[start:start + chunk_size]).strip()
        if value:
            windows.append(value)
        if start + chunk_size >= len(words):
            break
    return windows


def chunk(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    """Pack natural paragraphs into word-bounded chunks.

    Paragraph boundaries are retained when possible. A paragraph that exceeds
    ``chunk_size`` is split into overlapping word windows.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    text = text.strip()
    if not text:
        return []

    paragraphs = [
        " ".join(part.split())
        for part in _PARAGRAPH_BREAK.split(text)
        if part.strip()
    ]
    chunks: list[str] = []
    buffered: list[str] = []
    buffered_words = 0

    def flush_buffer() -> None:
        nonlocal buffered, buffered_words
        if buffered:
            chunks.append("\n\n".join(buffered))
            buffered = []
            buffered_words = 0

    for paragraph in paragraphs:
        words = paragraph.split()
        if len(words) > chunk_size:
            flush_buffer()
            chunks.extend(_word_windows(words, chunk_size, overlap))
            continue

        if buffered and buffered_words + len(words) > chunk_size:
            flush_buffer()

        buffered.append(paragraph)
        buffered_words += len(words)

    flush_buffer()
    return chunks
