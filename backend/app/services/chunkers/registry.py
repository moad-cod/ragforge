from enum import Enum
from app.services.chunkers import (
    fixed_size, paragraph, sentence,
    proposition, semantic, late_chunking, hierarchical
)

class ChunkerType(str, Enum):
    fixed_size    = "fixed_size"
    paragraph     = "paragraph"
    sentence      = "sentence"
    proposition   = "proposition"
    semantic      = "semantic"
    late_chunking = "late_chunking"
    hierarchical  = "hierarchical"     # ← new

CHUNKERS = {
    ChunkerType.fixed_size:    fixed_size.chunk,
    ChunkerType.paragraph:     paragraph.chunk,
    ChunkerType.sentence:      sentence.chunk,
    ChunkerType.proposition:   proposition.chunk,
    ChunkerType.semantic:      semantic.chunk,
    ChunkerType.late_chunking: late_chunking.chunk,
    ChunkerType.hierarchical:  hierarchical.chunk,  # ← new
}

def get_chunker(chunker_type: ChunkerType):
    return CHUNKERS[chunker_type]