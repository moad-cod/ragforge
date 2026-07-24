import fitz
from io import BytesIO
from threading import Lock

from PIL import Image

from app.services.storage import upload_image


_col_model = None
_col_processor = None
_model_lock = Lock()


def _get_model():
    global _col_model, _col_processor
    if _col_model is None or _col_processor is None:
        with _model_lock:
            if _col_model is None or _col_processor is None:
                import torch
                from colpali_engine.models import ColQwen2, ColQwen2Processor

                device = "cuda" if torch.cuda.is_available() else "cpu"
                model = ColQwen2.from_pretrained(
                    "vidore/colqwen2-v1.0",
                    torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                ).to(device).eval()
                processor = ColQwen2Processor.from_pretrained(
                    "vidore/colqwen2-v1.0"
                )
                _col_model = model
                _col_processor = processor
    return _col_model, _col_processor


def render_pdf_pages(file_bytes: bytes, dpi: int = 150, max_pages: int | None = None) -> list[Image.Image]:
    if not file_bytes:
        raise ValueError("PDF data is empty")
    if dpi <= 0:
        raise ValueError("dpi must be positive")
    if max_pages is not None and max_pages <= 0:
        raise ValueError("max_pages must be positive")

    pages: list[Image.Image] = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        if max_pages is not None and len(doc) > max_pages:
            raise ValueError(f"PDF has too many pages. Max is {max_pages}")
        if len(doc) == 0:
            raise ValueError("PDF contains no pages")

        matrix = fitz.Matrix(dpi / 72, dpi / 72)
        for page in doc:
            pixmap = page.get_pixmap(
                matrix=matrix,
                colorspace=fitz.csRGB,
                alpha=False,
            )
            pages.append(
                Image.frombytes(
                    "RGB",
                    (pixmap.width, pixmap.height),
                    pixmap.samples,
                )
            )
    return pages


def image_to_bytes(img: Image.Image) -> bytes:
    buf = BytesIO()
    image = img if img.mode in {"RGB", "RGBA", "L"} else img.convert("RGB")
    image.save(buf, format="PNG")
    return buf.getvalue()


def embed_pages(
    pages: list[Image.Image],
    batch_size: int = 2,
) -> list[list[list[float]]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if not pages:
        return []

    import torch

    model, processor = _get_model()
    device = next(model.parameters()).device
    all_embeddings: list[list[list[float]]] = []

    for i in range(0, len(pages), batch_size):
        batch = pages[i:i + batch_size]
        with torch.no_grad():
            inputs = processor.process_images(batch).to(device)
            embeddings = model(**inputs)
            for emb in embeddings:
                all_embeddings.append(emb.cpu().float().numpy().tolist())

    if len(all_embeddings) != len(pages):
        raise ValueError("multimodal model returned an unexpected number of page embeddings")
    return all_embeddings


def embed_query_tokens(query: str) -> list[list[float]]:
    if not query or not query.strip():
        raise ValueError("query must not be blank")

    import torch

    model, processor = _get_model()
    device = next(model.parameters()).device
    with torch.no_grad():
        inputs = processor.process_queries([query.strip()]).to(device)
        embeddings = model(**inputs)
        return embeddings[0].cpu().float().numpy().tolist()


def ingest_pdf_multimodal(
    file_bytes: bytes,
    document_id: str,
    max_pages: int | None = None,
) -> tuple[list[list[list[float]]], list[str], int]:
    if not document_id or not document_id.strip():
        raise ValueError("document_id must not be blank")

    pages = render_pdf_pages(file_bytes, max_pages=max_pages)
    page_embeddings = embed_pages(pages)

    page_image_urls: list[str] = []
    for i, page_img in enumerate(pages):
        img_bytes = image_to_bytes(page_img)
        key = f"pages/{document_id}/page_{i + 1}.png"
        url = upload_image(img_bytes, key)
        page_image_urls.append(url)

    return page_embeddings, page_image_urls, len(pages)
