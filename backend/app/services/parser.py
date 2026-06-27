import fitz  

def parse_document(file_bytes: bytes, filename: str) -> list[str]:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    chunks = []
    for page in doc:
        text = page.get_text()
        # Split into paragraphs, skip short ones
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 50]
        chunks.extend(paragraphs)
    
    return chunks