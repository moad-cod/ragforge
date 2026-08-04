from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import inspect
import re
import time
from typing import Any

import numpy as np

from app.core.config import settings


_model = None
_model_name: str | None = None
_model_loaded_at: float | None = None
_DETERMINISTIC_VECTOR_SIZE = 384
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")


@dataclass(frozen=True)
class EmbeddingModelInfo:
    backend: str
    model: str
    device: str
    dimension: int
    loaded: bool
    load_elapsed_ms: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _configured_model_name(model_name: str | None = None) -> str:
    return model_name or settings.EMBEDDING_MODEL


def resolve_embedding_device() -> str:
    configured = (settings.EMBEDDING_DEVICE or "auto").strip().lower()
    if configured == "auto":
        return "cpu"
    if configured not in {"cpu", "cuda", "mps"}:
        raise ValueError(
            f"Unsupported embedding device {settings.EMBEDDING_DEVICE!r}; "
            "expected auto, cpu, cuda, or mps"
        )
    if configured in {"cuda", "mps"}:
        raise RuntimeError(
            f"Embedding device {configured!r} is not available in the default local FastEmbed runtime. "
            "Use EMBEDDING_DEVICE=cpu or provide a worker image with that device support."
        )
    return configured


def _fastembed_class():
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise RuntimeError(
            "fastembed is required when EMBEDDING_BACKEND=fastembed. "
            "Use EMBEDDING_BACKEND=deterministic for offline smoke tests."
        ) from exc
    return TextEmbedding


def _fastembed_kwargs(TextEmbedding, model_name: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"model_name": model_name}
    parameters = inspect.signature(TextEmbedding).parameters
    if settings.EMBEDDING_CACHE_DIR and "cache_dir" in parameters:
        kwargs["cache_dir"] = settings.EMBEDDING_CACHE_DIR
    if not settings.EMBEDDING_ALLOW_MODEL_DOWNLOAD:
        if "local_files_only" not in parameters:
            raise RuntimeError(
                "EMBEDDING_ALLOW_MODEL_DOWNLOAD=false requires a FastEmbed version "
                "that supports local_files_only."
            )
        kwargs["local_files_only"] = True
    return kwargs


def get_embedding_model(model_name: str | None = None):
    """Return one local FastEmbed model instance per worker process."""
    global _model, _model_loaded_at, _model_name
    configured = _configured_model_name(model_name)
    if _model is not None and _model_name == configured:
        return _model

    TextEmbedding = _fastembed_class()
    _model = TextEmbedding(**_fastembed_kwargs(TextEmbedding, configured))
    _model_name = configured
    _model_loaded_at = time.monotonic()
    return _model


def get_embedding_model_info(model_name: str | None = None) -> EmbeddingModelInfo:
    configured = _configured_model_name(model_name)
    loaded = settings.EMBEDDING_BACKEND == "deterministic" or (
        _model is not None and _model_name == configured
    )
    return EmbeddingModelInfo(
        backend=settings.EMBEDDING_BACKEND,
        model=configured,
        device=resolve_embedding_device(),
        dimension=settings.EMBEDDING_DIMENSION,
        loaded=loaded,
    )


def ensure_embedding_model_ready(model_name: str | None = None) -> EmbeddingModelInfo:
    """Load/validate the configured embedding backend before chunk batches start."""
    configured = _configured_model_name(model_name)
    if settings.EMBEDDING_BACKEND == "deterministic":
        return get_embedding_model_info(configured)
    if settings.EMBEDDING_BACKEND != "fastembed":
        raise ValueError(f"Unsupported embedding backend {settings.EMBEDDING_BACKEND!r}")

    started = time.monotonic()
    resolve_embedding_device()
    get_embedding_model(configured)
    info = get_embedding_model_info(configured)
    return EmbeddingModelInfo(
        backend=info.backend,
        model=info.model,
        device=info.device,
        dimension=info.dimension,
        loaded=True,
        load_elapsed_ms=int((time.monotonic() - started) * 1000),
    )


def _normalize(vector) -> list[float]:
    arr = np.asarray(vector, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm:
        arr = arr / norm
    return arr.tolist()


def _deterministic_embedding(text: str) -> list[float]:
    """Produce a stable lexical vector for offline integration environments."""
    vector = np.zeros(_DETERMINISTIC_VECTOR_SIZE, dtype=np.float32)
    for token in _TOKEN_PATTERN.findall(text.lower()):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest, "big") % _DETERMINISTIC_VECTOR_SIZE
        vector[index] += 1.0
    return _normalize(vector)


def embed_texts(texts: list[str], *, model_name: str | None = None) -> list[list[float]]:
    if not texts:
        return []
    if settings.EMBEDDING_BACKEND == "deterministic":
        return [_deterministic_embedding(text) for text in texts]
    if settings.EMBEDDING_BACKEND != "fastembed":
        raise ValueError(f"Unsupported embedding backend {settings.EMBEDDING_BACKEND!r}")
    model = get_embedding_model(model_name)
    return [_normalize(vector) for vector in model.passage_embed(texts)]


def embed_query(query: str) -> list[float]:
    if settings.EMBEDDING_BACKEND == "deterministic":
        return _deterministic_embedding(query)
    if settings.EMBEDDING_BACKEND != "fastembed":
        raise ValueError(f"Unsupported embedding backend {settings.EMBEDDING_BACKEND!r}")
    return _normalize(next(get_embedding_model().query_embed([query])))
