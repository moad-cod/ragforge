import nltk
from dataclasses import dataclass

@dataclass
class HierarchicalChunk:
    text: str
    chunk_type: str      
    parent_id: str | None
    chunk_id: str
    index: int

def chunk(text: str) -> list[str]:
    """
    Standard interface — returns only child chunks as strings.
    Use chunk_hierarchical() for full parent/child structure.
    """
    pairs = chunk_hierarchical(text)
    return [c.text for c in pairs if c.chunk_type == "child"]


def chunk_hierarchical(
    text: str,
    parent_size: int = 5,    # sentences per parent
    child_size: int = 2,     # sentences per child
) -> list[HierarchicalChunk]:
    """
    Returns full hierarchy — both parent and child chunks with relationships.
    """
    import uuid

    sentences = [s.strip() for s in nltk.sent_tokenize(text) if len(s.strip()) > 20]
    if not sentences:
        return []

    chunks = []
    parent_index = 0

    for p_start in range(0, len(sentences), parent_size):
        parent_sentences = sentences[p_start:p_start + parent_size]
        parent_text = " ".join(parent_sentences).strip()
        if len(parent_text) < 30:
            continue

        parent_id = str(uuid.uuid4())

        # store parent
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