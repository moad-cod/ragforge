import numpy as np
from app.services.embedder import embed_texts
from app.services.chunkers.tokenize import split_sentences

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))

def chunk(text: str, threshold: float = 0.5, min_chunk_len: int = 50) -> list[str]:
    """
    Split text into semantically coherent chunks.
    A new chunk starts when the similarity between adjacent
    sentences drops below the threshold.
    """
    # 1. split into sentences
    sentences = [s.strip() for s in split_sentences(text) if len(s.strip()) > 20]
    if not sentences:
        return []
    if len(sentences) == 1:
        return sentences

    # 2. embed all sentences at once (fast batch)
    embeddings = np.array(embed_texts(sentences))

    # 3. find split points where similarity drops
    chunks = []
    current = [sentences[0]]

    for i in range(1, len(sentences)):
        sim = _cosine_similarity(embeddings[i - 1], embeddings[i])
        if sim >= threshold:
            # same topic — keep in current chunk
            current.append(sentences[i])
        else:
            # topic shift — save current chunk, start new one
            chunk_text = " ".join(current).strip()
            if len(chunk_text) >= min_chunk_len:
                chunks.append(chunk_text)
            current = [sentences[i]]

    # 4. don't forget the last chunk
    if current:
        chunk_text = " ".join(current).strip()
        if len(chunk_text) >= min_chunk_len:
            chunks.append(chunk_text)

    return chunks
