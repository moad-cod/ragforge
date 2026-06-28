def chunk(text: str) -> list[str]:
    words = text.split()
    chunk_size = 400
    overlap = 50
    chunks = []

    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        if len(chunk.strip()) > 50:
            chunks.append(chunk)
        i += chunk_size - overlap

    return chunks