from dataclasses import dataclass
import uuid

from app.services.chunkers.tokenize import split_sentences


@dataclass
class HierarchicalChunk:
    text: str
    chunk_type: str
    parent_id: str | None
    chunk_id: str
    index: int


def chunk(text: str) -> list[str]:
    """Return child text for the common text-chunker interface."""
    pairs = chunk_hierarchical(text)
    return [c.text for c in pairs if c.chunk_type == "child"]


def chunk_hierarchical(
    text: str,
    parent_size: int = 5,
    child_size: int = 2,
    namespace: str | None = None,
) -> list[HierarchicalChunk]:
    """Return deterministic parent and child records grouped by sentence count."""
    if parent_size <= 0:
        raise ValueError("parent_size must be positive")
    if child_size <= 0:
        raise ValueError("child_size must be positive")

    sentences = split_sentences(text)
    if not sentences:
        return []

    id_namespace = namespace or text
    chunks: list[HierarchicalChunk] = []
    parent_index = 0

    for p_start in range(0, len(sentences), parent_size):
        parent_sentences = sentences[p_start:p_start + parent_size]
        parent_text = " ".join(parent_sentences).strip()
        parent_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"ragforge:hierarchical:{id_namespace}:parent:{p_start}:{parent_text}",
            )
        )
        chunks.append(HierarchicalChunk(
            text=parent_text,
            chunk_type="parent",
            parent_id=None,
            chunk_id=parent_id,
            index=parent_index,
        ))

        # split parent into children
        child_index = 0
        for c_start in range(0, len(parent_sentences), child_size):
            child_sentences = parent_sentences[c_start:c_start + child_size]
            child_text = " ".join(child_sentences).strip()
            if len(child_text) < 20:
                continue

            chunks.append(HierarchicalChunk(
                text=child_text,
                chunk_type="child",
                parent_id=parent_id,
                chunk_id=str(uuid.uuid4()),
                index=child_index,
            ))
            child_index += 1

        parent_index += 1

    return chunks
