"""Durable PostgreSQL-to-Qdrant chunk lineage for control-plane ingestion."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import hashlib
import uuid
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct, SparseVector
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, Document, DocumentVersion, IngestionRun, Project
from app.repositories.chunks import replace_chunks_for_document_version
from app.services.indexer import ensure_collection, qdrant
from app.services.retrieval.sparse import embed_sparse


# Qdrant point IDs must be UUIDs or unsigned integers. The readable lineage key
# is converted to UUIDv5 so the same document version can always be rebuilt.
QDRANT_CHUNK_NAMESPACE = uuid.UUID("5ce0fb34-9d58-4cf5-98b6-b98445370f8f")
POSTGRES_CHUNK_NAMESPACE = uuid.UUID("e62ecb19-92a1-4679-a4a0-f4cd5b8a1397")


@dataclass(frozen=True)
class GoldChunk:
    """One embedded chunk read from a Gold artifact."""

    chunk_index: int
    text: str
    dense_vector: Sequence[float]
    content_hash: str | None = None
    token_count: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    section_title: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


def chunk_lineage_id(document_version_id: str, chunk_index: int) -> str:
    if chunk_index < 0:
        raise ValueError("chunk_index must be non-negative")
    return f"{document_version_id}:{chunk_index}"


def qdrant_point_id(document_version_id: str, chunk_index: int) -> str:
    return str(uuid.uuid5(QDRANT_CHUNK_NAMESPACE, chunk_lineage_id(document_version_id, chunk_index)))


def postgres_chunk_id(document_version_id: str, chunk_index: int) -> str:
    return str(uuid.uuid5(POSTGRES_CHUNK_NAMESPACE, chunk_lineage_id(document_version_id, chunk_index)))


def _content_hash(chunk: GoldChunk) -> str:
    return chunk.content_hash or hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()


def _validate_chunks(chunks: Sequence[GoldChunk]) -> None:
    if not chunks:
        raise ValueError("At least one Gold chunk is required for indexing")

    indexes: set[int] = set()
    hashes: set[str] = set()
    vector_size: int | None = None
    for chunk in chunks:
        if not chunk.text.strip():
            raise ValueError(f"Chunk {chunk.chunk_index} has no indexable text")
        if chunk.chunk_index in indexes:
            raise ValueError(f"Duplicate chunk_index {chunk.chunk_index}")
        indexes.add(chunk.chunk_index)

        content_hash = _content_hash(chunk)
        if content_hash in hashes:
            raise ValueError(f"Duplicate content_hash for chunk {chunk.chunk_index}")
        hashes.add(content_hash)

        if len(chunk.dense_vector) == 0:
            raise ValueError(f"Chunk {chunk.chunk_index} has no dense vector")
        if vector_size is None:
            vector_size = len(chunk.dense_vector)
        elif len(chunk.dense_vector) != vector_size:
            raise ValueError("All dense vectors must have the same size")


def _chunk_values(
    *,
    project: Project,
    document: Document,
    version: DocumentVersion,
    ingestion_run: IngestionRun | None,
    chunk: GoldChunk,
) -> dict[str, Any]:
    return {
        "id": postgres_chunk_id(version.id, chunk.chunk_index),
        "project_id": project.id,
        "document_id": document.id,
        "document_version_id": version.id,
        "ingestion_run_id": ingestion_run.id if ingestion_run else None,
        "qdrant_point_id": qdrant_point_id(version.id, chunk.chunk_index),
        "chunk_index": chunk.chunk_index,
        "text": chunk.text,
        "content_hash": _content_hash(chunk),
        "token_count": chunk.token_count,
        "page_start": chunk.page_start,
        "page_end": chunk.page_end,
        "section_title": chunk.section_title,
        "metadata_json": dict(chunk.metadata) or None,
    }


def _payload(
    *,
    project: Project,
    document: Document,
    version: DocumentVersion,
    chunk: GoldChunk,
    values: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "organization_id": project.organization_id,
        "project_id": project.id,
        "document_id": document.id,
        "document_version_id": version.id,
        "chunk_id": values["id"],
        "qdrant_point_id": values["qdrant_point_id"],
        "lineage_id": chunk_lineage_id(version.id, chunk.chunk_index),
        "chunk_index": chunk.chunk_index,
        "title": document.filename,
        "source_type": document.source_type,
        "page_start": chunk.page_start,
        "page_end": chunk.page_end,
        "section_title": chunk.section_title,
        "text": chunk.text,
        "metadata": dict(chunk.metadata),
    }


def _replace_qdrant_version(
    *,
    client: QdrantClient,
    collection: str,
    version_id: str,
    points: Sequence[PointStruct],
    vector_size: int,
) -> None:
    ensure_collection(collection, vector_size=vector_size, client=client)
    client.delete(
        collection_name=collection,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="document_version_id",
                    match=MatchValue(value=version_id),
                )
            ]
        ),
        wait=True,
    )
    client.upsert(collection_name=collection, points=list(points), wait=True)


async def index_document_version_chunks(
    db: AsyncSession,
    *,
    project: Project,
    document: Document,
    version: DocumentVersion,
    ingestion_run: IngestionRun | None,
    chunks: Sequence[GoldChunk],
    client: QdrantClient | None = None,
    sparse_embedder: Callable[[list[str]], list[SparseVector]] = embed_sparse,
) -> list[Chunk]:
    """Rebuild one version in Qdrant and replace its PostgreSQL chunk rows.

    The caller owns the SQL transaction. Qdrant is updated first; if the SQL
    flush fails, a retry is safe because all IDs are deterministic.
    """
    _validate_chunks(chunks)
    if document.project_id != project.id:
        raise ValueError("Document does not belong to the supplied project")
    if version.document_id != document.id:
        raise ValueError("Document version does not belong to the supplied document")
    if ingestion_run is not None and ingestion_run.document_version_id != version.id:
        raise ValueError("Ingestion run does not belong to the supplied document version")

    sparse_vectors = await asyncio.to_thread(sparse_embedder, [chunk.text for chunk in chunks])
    if len(sparse_vectors) != len(chunks):
        raise ValueError("Sparse embedder returned an unexpected number of vectors")

    rows: list[dict[str, Any]] = []
    points: list[PointStruct] = []
    for chunk, sparse_vector in zip(chunks, sparse_vectors):
        values = _chunk_values(
            project=project,
            document=document,
            version=version,
            ingestion_run=ingestion_run,
            chunk=chunk,
        )
        rows.append(values)
        points.append(
            PointStruct(
                id=values["qdrant_point_id"],
                vector={"dense": list(chunk.dense_vector), "sparse": sparse_vector},
                payload=_payload(
                    project=project,
                    document=document,
                    version=version,
                    chunk=chunk,
                    values=values,
                ),
            )
        )

    await asyncio.to_thread(
        _replace_qdrant_version,
        client=client or qdrant,
        collection=project.qdrant_collection,
        version_id=version.id,
        points=points,
        vector_size=len(chunks[0].dense_vector),
    )
    return await replace_chunks_for_document_version(db, version.id, rows)


async def rebuild_document_version_index(*args: Any, **kwargs: Any) -> list[Chunk]:
    """Explicit rebuild entry point for Gold artifact recovery jobs."""
    return await index_document_version_chunks(*args, **kwargs)
