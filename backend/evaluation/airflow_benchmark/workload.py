"""Benchmark workload construction for the current Airflow pipeline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from evaluation.airflow_benchmark.models import WorkloadDocument


PROFILE_BY_CHUNKER = {
    "fixed_size": "throughput",
    "paragraph": "throughput",
    "sentence": "throughput",
    "hierarchical": "structured",
    "semantic": "embedding_aware",
    "late_chunking": "embedding_aware",
    "proposition": "llm_enriched",
}


def deterministic_text(marker: str, *, paragraphs: int = 12) -> bytes:
    paragraph = (
        f"{marker} verifies the RAGForge Airflow ingestion path from Bronze storage "
        "through Silver chunks, Gold embeddings, Qdrant indexing, and PostgreSQL "
        "control-plane finalization. The benchmark checks correctness, latency, "
        "retry safety, and lineage without changing pipeline business logic."
    )
    return "\n\n".join(paragraph for _ in range(paragraphs)).encode("utf-8")


def build_default_workload(
    *,
    document_count: int,
    chunker: str,
    dataset_version: str,
) -> list[WorkloadDocument]:
    profile = PROFILE_BY_CHUNKER.get(chunker, "custom")
    return [
        WorkloadDocument(
            document_id=f"{dataset_version}-airflow-{index + 1:04d}",
            filename=f"{dataset_version}-airflow-{index + 1:04d}.txt",
            content=deterministic_text(f"{dataset_version}_airflow_doc_{index + 1:04d}"),
            mime_type="text/plain",
            chunker=chunker,
            profile=profile,
        )
        for index in range(document_count)
    ]


def load_manifest(path: Path, *, fallback_chunker: str) -> list[WorkloadDocument]:
    payload: dict[str, Any] = json.loads(path.read_text())
    root = path.parent.parent if path.parent.name == "manifests" else path.parent
    documents: list[WorkloadDocument] = []
    for item in payload.get("documents", []):
        filename = str(item["filename"])
        relative_path = item.get("path") or filename
        content = (root / relative_path).read_bytes()
        sha256 = hashlib.sha256(content).hexdigest()
        expected_sha256 = item.get("sha256")
        if expected_sha256 and sha256 != expected_sha256:
            raise ValueError(f"Manifest hash mismatch for {filename}: {sha256} != {expected_sha256}")
        chunker = str(item.get("chunker") or fallback_chunker)
        documents.append(
            WorkloadDocument(
                document_id=str(item.get("document_id") or filename),
                filename=filename,
                content=content,
                mime_type=str(item.get("mime_type") or "application/octet-stream"),
                chunker=chunker,
                profile=str(item.get("profile") or PROFILE_BY_CHUNKER.get(chunker, "custom")),
            )
        )
    return documents
