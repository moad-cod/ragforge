import nltk
    
def chunk(text: str) -> list[str]:
    sentences = nltk.sent_tokenize(text)
    # Filter very short sentences (noise)
    return [s.strip() for s in sentences if len(s.strip()) > 30]