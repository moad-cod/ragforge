# app/services/chunkers/multimodal.py

import fitz
import torch
import numpy as np
from PIL import Image
from io import BytesIO
from app.services.storage import upload_image

# ── lazy model loading ────────────────────────────────────────────────────────
_col_model = None
_col_processor = None

def _get_model():
    global _col_model, _col_processor
    if _col_model is None:
        from colpali_engine.models import ColQwen2, ColQwen2Processor
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading ColQwen2 on {device}...")
        _col_model = ColQwen2.from_pretrained(
            "vidore/colqwen2-v1.0",
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        ).to(device).eval()
        _col_processor = ColQwen2Processor.from_pretrained("vidore/colqwen2-v1.0")
        print("✅ ColQwen2 ready")
    return _col_model, _col_processor


# ── render PDF pages ──────────────────────────────────────────────────────────

def render_pdf_pages(file_bytes: bytes, dpi: int = 150) -> list[Image.Image]:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    for page in doc:
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        pages.append(img)
    return pages

def image_to_bytes(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── embed pages ───────────────────────────────────────────────────────────────

def embed_pages(pages: list[Image.Image]) -> list[list[list[float]]]:
    model, processor = _get_model()   # ← loads only when called
    device = next(model.parameters()).device
    all_embeddings = []
    batch_size = 2   # smaller batch for CPU

    for i in range(0, len(pages), batch_size):
        batch = pages[i:i + batch_size]
        with torch.no_grad():
            inputs = processor.process_images(batch).to(device)
            embeddings = model(**inputs)
            for emb in embeddings:
                all_embeddings.append(emb.cpu().float().numpy().tolist())

    return all_embeddings


# ── embed query tokens ────────────────────────────────────────────────────────

def embed_query_tokens(query: str) -> list[list[float]]:
    model, processor = _get_model()   # ← loads only when called
    device = next(model.parameters()).device
    with torch.no_grad():
        inputs = processor.process_queries([query]).to(device)
        embeddings = model(**inputs)
        return embeddings[0].cpu().float().numpy().tolist()


# ── main ingest ───────────────────────────────────────────────────────────────

def ingest_pdf_multimodal(
    file_bytes: bytes,
    document_id: str,
) -> tuple[list[list[list[float]]], list[str], int]:
    pages = render_pdf_pages(file_bytes)
    page_embeddings = embed_pages(pages)   # ← model loads here, first call only

    page_image_urls = []
    for i, page_img in enumerate(pages):
        img_bytes = image_to_bytes(page_img)
        key = f"pages/{document_id}/page_{i + 1}.png"
        url = upload_image(img_bytes, key)
        page_image_urls.append(url)

    return page_embeddings, page_image_urls, len(pages)