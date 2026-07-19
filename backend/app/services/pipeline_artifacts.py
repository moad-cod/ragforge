"""Bronze, Silver, and Gold artifact transformations for batch ingestion."""

from __future__ import annotations

import hashlib
import io
import json
import os
from collections.abc import Callable, Sequence
from typing import Any

import boto3
from botocore.config import Config


SILVER_FILENAME = "chunks.parquet"
GOLD_FILENAME = "embedded_chunks.parquet"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


def _split_object_path(path: str) -> tuple[str, str]:
    bucket, separator, key = (path or "").partition("/")
    if not separator or not bucket or not key:
        raise ValueError(f"Invalid object path {path!r}; expected bucket/key")
    return bucket, key


def derive_artifact_path(bronze_path: str, bucket: str, filename: str) -> str:
    """Derive a deterministic sibling path from a versioned Bronze object."""
    _bronze_bucket, bronze_key = _split_object_path(bronze_path)
    prefix, marker, _raw_name = bronze_key.rpartition("/raw/")
    if not marker or not prefix:
        raise ValueError(f"Bronze path {bronze_path!r} does not contain a versioned /raw/ key")
    return f"{bucket}/{prefix}/{filename}"


class ArtifactStore:
    """Small S3-compatible object store used by the pipeline commands."""

    def __init__(self, client=None) -> None:
        self.client = client or boto3.client(
            "s3",
            endpoint_url=_minio_endpoint(),
            aws_access_key_id=os.environ.get("MINIO_ACCESS_KEY", "ragforge"),
            aws_secret_access_key=os.environ.get("MINIO_SECRET_KEY", "ragforge123"),
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )

    def read_bytes(self, path: str) -> bytes:
        bucket, key = _split_object_path(path)
        return self.client.get_object(Bucket=bucket, Key=key)["Body"].read()

    def write_bytes(self, path: str, data: bytes, content_type: str) -> str:
        bucket, key = _split_object_path(path)
        self.client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
        return path


def _minio_endpoint() -> str:
    endpoint = os.environ.get("MINIO_ENDPOINT", "http://minio:9000").rstrip("/")
    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"http://{endpoint}"
    return endpoint


def _parquet_modules():
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("pyarrow is required by the ingestion artifact jobs") from exc
    return pa, pq


def _silver_schema():
    pa, _pq = _parquet_modules()
    return pa.schema(
        [
            ("chunk_index", pa.int64()),
            ("text", pa.string()),
            ("content_hash", pa.string()),
            ("token_count", pa.int64()),
            ("page_start", pa.int64()),
            ("page_end", pa.int64()),
            ("section_title", pa.string()),
            ("metadata_json", pa.string()),
            # Late chunking creates context-aware vectors while it identifies
            # chunk boundaries. Preserve them so Gold does not recompute a
            # less contextual embedding for the same text.
            ("precomputed_dense_vector", pa.list_(pa.float32())),
        ]
    )


def _gold_schema():
    pa, _pq = _parquet_modules()
    return pa.schema(
        [
            field
            for field in _silver_schema()
            if field.name != "precomputed_dense_vector"
        ]
    ).append(pa.field("dense_vector", pa.list_(pa.float32())))


def _write_parquet(rows: Sequence[dict[str, Any]], schema) -> bytes:
    pa, pq = _parquet_modules()
    buffer = io.BytesIO()
    table = pa.Table.from_pylist(list(rows), schema=schema)
    pq.write_table(table, buffer, compression="zstd")
    return buffer.getvalue()


def _read_parquet(data: bytes) -> list[dict[str, Any]]:
    _pa, pq = _parquet_modules()
    return pq.read_table(io.BytesIO(data)).to_pylist()


def build_silver_rows(
    raw_bytes: bytes,
    *,
    filename: str,
    chunker_id: str,
    parser: Callable[[bytes, str], list[str]] | None = None,
    chunker_loader: Callable[[str], Callable[[str], list[str]]] | None = None,
) -> list[dict[str, Any]]:
    use_builtin_chunker = chunker_loader is None
    if parser is None:
        from app.services.parser import parse_document

        parser = parse_document
    if chunker_loader is None:
        from app.services.chunkers.registry import get_chunker

        chunker_loader = get_chunker

    parsed_sections = parser(raw_bytes, filename)
    full_text = "\n\n".join(parsed_sections)
    precomputed_vectors = None
    if chunker_id == "late_chunking" and use_builtin_chunker:
        from app.services.chunkers.late_chunking import chunk_with_embeddings

        chunks, precomputed_vectors = chunk_with_embeddings(full_text)
    else:
        chunks = chunker_loader(chunker_id)(full_text)
    rows = []
    for index, chunk in enumerate(chunks):
        text = str(getattr(chunk, "text", chunk)).strip()
        if not text:
            continue
        rows.append(
            {
                "chunk_index": index,
                "text": text,
                "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "token_count": None,
                "page_start": None,
                "page_end": None,
                "section_title": None,
                "metadata_json": json.dumps(
                    {"parser_filename": filename, "chunker_id": chunker_id},
                    sort_keys=True,
                ),
                "precomputed_dense_vector": (
                    [float(value) for value in precomputed_vectors[index]]
                    if precomputed_vectors is not None
                    else None
                ),
            }
        )
    if not rows:
        raise ValueError("No indexable text was extracted from the Bronze object")
    return rows


def bronze_to_silver(
    run: dict[str, Any],
    *,
    store: ArtifactStore | None = None,
    parser: Callable[[bytes, str], list[str]] | None = None,
    chunker_loader: Callable[[str], Callable[[str], list[str]]] | None = None,
) -> dict[str, Any]:
    store = store or ArtifactStore()
    bronze_path = run.get("bronze_path")
    if not bronze_path:
        raise ValueError("Ingestion metadata has no Bronze path")
    filename = run.get("filename") or "upload"
    chunker_id = run.get("chunker_id") or "paragraph"
    rows = build_silver_rows(
        store.read_bytes(bronze_path),
        filename=filename,
        chunker_id=chunker_id,
        parser=parser,
        chunker_loader=chunker_loader,
    )
    silver_path = run.get("silver_path") or derive_artifact_path(
        bronze_path,
        os.environ.get("MINIO_BUCKET_SILVER", "silver"),
        SILVER_FILENAME,
    )
    store.write_bytes(
        silver_path,
        _write_parquet(rows, _silver_schema()),
        "application/vnd.apache.parquet",
    )
    return {"artifact_path": silver_path, "chunks": len(rows)}


def silver_to_gold(
    run: dict[str, Any],
    *,
    store: ArtifactStore | None = None,
    embedder: Callable[[list[str]], list[list[float]]] | None = None,
) -> dict[str, Any]:
    store = store or ArtifactStore()
    silver_path = run.get("silver_path")
    if not silver_path:
        raise ValueError("Ingestion metadata has no Silver path")
    rows = _read_parquet(store.read_bytes(silver_path))
    if not rows:
        raise ValueError("Silver artifact contains no chunks")
    if embedder is None:
        embedding_model = run.get("embedding_model") or DEFAULT_EMBEDDING_MODEL
        if embedding_model != DEFAULT_EMBEDDING_MODEL:
            raise ValueError(f"Unsupported pipeline embedding model {embedding_model!r}")
        from app.services.embedder import embed_texts

        embedder = embed_texts
    embeddings = embedder([row["text"] for row in rows])
    if len(embeddings) != len(rows):
        raise ValueError("Embedding model returned an unexpected number of vectors")
    gold_rows = [
        {**row, "dense_vector": [float(value) for value in vector]}
        for row, vector in zip(rows, embeddings)
    ]
    bronze_path = run.get("bronze_path")
    if not bronze_path:
        raise ValueError("Ingestion metadata has no Bronze path")
    gold_path = run.get("gold_path") or derive_artifact_path(
        bronze_path,
        os.environ.get("MINIO_BUCKET_GOLD", "gold"),
        GOLD_FILENAME,
    )
    store.write_bytes(
        gold_path,
        _write_parquet(gold_rows, _gold_schema()),
        "application/vnd.apache.parquet",
    )
    return {"artifact_path": gold_path, "chunks": len(gold_rows)}


def gold_chunks(run: dict[str, Any], *, store: ArtifactStore | None = None) -> list[dict]:
    store = store or ArtifactStore()
    gold_path = run.get("gold_path")
    if not gold_path:
        raise ValueError("Ingestion metadata has no Gold path")
    rows = _read_parquet(store.read_bytes(gold_path))
    chunks = []
    for row in rows:
        metadata = json.loads(row.pop("metadata_json") or "{}")
        row["metadata"] = metadata
        chunks.append(row)
    if not chunks:
        raise ValueError("Gold artifact contains no chunks")
    return chunks
