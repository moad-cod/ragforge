from app.services.chunkers.tokenize import split_sentences
    
def chunk(text: str) -> list[str]:
    sentences = split_sentences(text)
    # Filter very short sentences (noise)
    return [s.strip() for s in sentences if len(s.strip()) > 30]
