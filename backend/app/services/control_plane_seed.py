"""Deterministic development seed data for the complete control plane."""

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Chunk,
    Document,
    DocumentVersion,
    EmbeddingRun,
    IngestionRun,
    Organization,
    Project,
    QueryLog,
    RetrievalLog,
    User,
)
from app.services.chunk_indexing import qdrant_point_id
from app.services.query_observability import normalized_question_hash


SEED_UUID_NAMESPACE = uuid.UUID("bc286dc4-06af-4d65-8603-b3d51d78bce0")


@dataclass(frozen=True)
class ControlPlaneSeed:
    organization_id: str
    user_id: str
    project_id: str
    document_id: str
    document_version_id: str
    ingestion_run_id: str
    embedding_run_id: str
    chunk_id: str
    query_log_id: str
    retrieval_log_id: str


def _seed_id(namespace: str, entity: str) -> str:
    return str(uuid.uuid5(SEED_UUID_NAMESPACE, f"{namespace}:{entity}"))


def _seed_slug(namespace: str) -> str:
    readable = re.sub(r"[^a-z0-9]+", "-", namespace.casefold()).strip("-") or "default"
    digest = hashlib.sha256(namespace.encode("utf-8")).hexdigest()[:10]
    return f"{readable[:32]}-{digest}"


async def _get_or_add(db: AsyncSession, model_class, identifier: str, **values):
    record = await db.get(model_class, identifier)
    if record is None:
        record = model_class(id=identifier, **values)
        db.add(record)
        await db.flush()
    return record


async def seed_control_plane(
    db: AsyncSession,
    *,
    namespace: str = "development",
) -> ControlPlaneSeed:
    """Insert one complete, repeatable control-plane graph without committing.

    Callers control the transaction. Reusing the same namespace returns the
    same records, which makes the command safe to run more than once.
    """
    namespace = namespace.strip() or "development"
    slug = _seed_slug(namespace)
    ids = {
        entity: _seed_id(namespace, entity)
        for entity in (
            "organization",
            "user",
            "project",
            "document",
            "document_version",
            "ingestion_run",
            "embedding_run",
            "chunk",
            "query_log",
            "retrieval_log",
        )
    }

    await _get_or_add(
        db,
        Organization,
        ids["organization"],
        name=f"RAGForge Seed {namespace}",
    )
    await _get_or_add(
        db,
        User,
        ids["user"],
        organization_id=ids["organization"],
        email=f"seed-{slug}@ragforge.local",
        full_name="RAGForge Seed User",
        hashed_password="seed-data-not-for-authentication",
    )
    await _get_or_add(
        db,
        Project,
        ids["project"],
        organization_id=ids["organization"],
        name=f"Seed Project {namespace}",
        qdrant_collection=f"ragforge_seed_{slug.replace('-', '_')}",
        created_by=ids["user"],
    )
    document = await _get_or_add(
        db,
        Document,
        ids["document"],
        project_id=ids["project"],
        source_type="file_upload",
        filename="control-plane-seed.txt",
        mime_type="text/plain",
        extension="txt",
        status="indexed",
        created_by=ids["user"],
    )
    await _get_or_add(
        db,
        DocumentVersion,
        ids["document_version"],
        document_id=ids["document"],
        version_number=1,
        content_hash=hashlib.sha256(f"{namespace}:document".encode()).hexdigest(),
        bronze_path=f"bronze/seed/{slug}/raw/control-plane-seed.txt",
        silver_path=f"silver/seed/{slug}/chunks.parquet",
        gold_path=f"gold/seed/{slug}/embedded_chunks.parquet",
        parser_name="text",
        chunker_id="paragraph",
        embedding_model="BAAI/bge-small-en-v1.5",
        status="indexed",
    )
    if document.current_version_id is None:
        document.current_version_id = ids["document_version"]
        await db.flush()

    now = datetime.now(UTC).replace(tzinfo=None)
    await _get_or_add(
        db,
        IngestionRun,
        ids["ingestion_run"],
        project_id=ids["project"],
        document_id=ids["document"],
        document_version_id=ids["document_version"],
        status="indexed",
        started_at=now,
        finished_at=now,
        airflow_dag_run_id=f"seed-{slug}",
        created_by=ids["user"],
    )
    await _get_or_add(
        db,
        EmbeddingRun,
        ids["embedding_run"],
        project_id=ids["project"],
        document_version_id=ids["document_version"],
        embedding_model="BAAI/bge-small-en-v1.5",
        status="completed",
        total_chunks=1,
        embedded_chunks=1,
        started_at=now,
        finished_at=now,
    )
    chunk_text = "RAGForge keeps durable control-plane state in PostgreSQL."
    await _get_or_add(
        db,
        Chunk,
        ids["chunk"],
        project_id=ids["project"],
        document_id=ids["document"],
        document_version_id=ids["document_version"],
        ingestion_run_id=ids["ingestion_run"],
        qdrant_point_id=qdrant_point_id(ids["document_version"], 0),
        chunk_index=0,
        text=chunk_text,
        content_hash=hashlib.sha256(chunk_text.encode()).hexdigest(),
        token_count=8,
        page_start=1,
        page_end=1,
        section_title="Control Plane",
        metadata_json={"seed_namespace": namespace},
    )
    question = "Where is durable control-plane state stored?"
    await _get_or_add(
        db,
        QueryLog,
        ids["query_log"],
        project_id=ids["project"],
        user_id=ids["user"],
        question=question,
        normalized_question_hash=normalized_question_hash(question),
        provider="groq",
        model="seed-model",
        latency_ms=25,
        cache_hit=False,
        route="rag",
    )
    await _get_or_add(
        db,
        RetrievalLog,
        ids["retrieval_log"],
        query_log_id=ids["query_log"],
        chunk_id=ids["chunk"],
        qdrant_score=0.97,
        rerank_score=0.91,
        rank=1,
        retrieval_strategy="hybrid",
        used_in_answer=True,
    )

    return ControlPlaneSeed(
        organization_id=ids["organization"],
        user_id=ids["user"],
        project_id=ids["project"],
        document_id=ids["document"],
        document_version_id=ids["document_version"],
        ingestion_run_id=ids["ingestion_run"],
        embedding_run_id=ids["embedding_run"],
        chunk_id=ids["chunk"],
        query_log_id=ids["query_log"],
        retrieval_log_id=ids["retrieval_log"],
    )
