from enum import Enum
from app.services.chunkers import fixed_size, paragraph, sentence, proposition, semantic

class ChunkerType(str, Enum):
    fixed_size  = "fixed_size"
    paragraph   = "paragraph"
    sentence    = "sentence"
    proposition = "proposition"
    semantic    = "semantic"

CHUNKERS = {
    ChunkerType.fixed_size:  fixed_size.chunk,
    ChunkerType.paragraph:   paragraph.chunk,
    ChunkerType.sentence:    sentence.chunk,
    ChunkerType.proposition: proposition.chunk,
    ChunkerType.semantic:    semantic.chunk,
}

def get_chunker(chunker_type: ChunkerType):
    return CHUNKERS[chunker_type]