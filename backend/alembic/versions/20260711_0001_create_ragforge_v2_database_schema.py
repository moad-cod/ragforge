"""create RAGForge v2 database schema

Revision ID: 20260711_0001
Revises:
Create Date: 2026-07-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260711_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DOCUMENT_STATUSES = (
    "uploaded", "landed", "processing", "chunked", "embedded", "indexed", "failed", "deleted"
)
INGESTION_STATUSES = (
    "landed", "queued", "running", "silver_completed", "gold_completed", "indexed", "failed", "cancelled"
)
EMBEDDING_STATUSES = ("queued", "running", "completed", "failed", "cancelled")


def _status_check(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("qdrant_collection", sa.String(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("qdrant_collection", name="uq_projects_qdrant_collection"),
    )
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"])
    op.create_index("ix_projects_created_by", "projects", ["created_by"])
    op.create_index("ix_projects_created_at", "projects", ["created_at"])
    op.create_index("ix_projects_deleted_at", "projects", ["deleted_at"])

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("source_type", sa.String(), nullable=True),
        sa.Column("filename", sa.String(), nullable=True),
        sa.Column("mime_type", sa.String(), nullable=True),
        sa.Column("extension", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(_status_check("status", DOCUMENT_STATUSES), name="ck_documents_status"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_project_id", "documents", ["project_id"])
    op.create_index("ix_documents_current_version_id", "documents", ["current_version_id"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_created_by", "documents", ["created_by"])
    op.create_index("ix_documents_created_at", "documents", ["created_at"])
    op.create_index("ix_documents_deleted_at", "documents", ["deleted_at"])

    op.create_table(
        "document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("bronze_path", sa.String(), nullable=True),
        sa.Column("silver_path", sa.String(), nullable=True),
        sa.Column("gold_path", sa.String(), nullable=True),
        sa.Column("parser_name", sa.String(), nullable=True),
        sa.Column("chunker_id", sa.String(), nullable=True),
        sa.Column("embedding_model", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "version_number", name="uq_document_versions_document_version_number"),
        sa.UniqueConstraint("document_id", "content_hash", name="uq_document_versions_document_content_hash"),
    )
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])
    op.create_index("ix_document_versions_status", "document_versions", ["status"])
    op.create_index("ix_document_versions_content_hash", "document_versions", ["content_hash"])
    op.create_index("ix_document_versions_created_at", "document_versions", ["created_at"])
    op.create_foreign_key(
        "fk_documents_current_version_id_document_versions",
        "documents", "document_versions", ["current_version_id"], ["id"], ondelete="SET NULL"
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("airflow_dag_run_id", sa.String(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(_status_check("status", INGESTION_STATUSES), name="ck_ingestion_runs_status"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("project_id", "document_id", "document_version_id", "status", "created_at", "airflow_dag_run_id"):
        op.create_index(f"ix_ingestion_runs_{column}", "ingestion_runs", [column])

    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("ingestion_run_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("qdrant_point_id", sa.String(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("section_title", sa.String(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("qdrant_point_id", name="uq_chunks_qdrant_point_id"),
        sa.UniqueConstraint("document_version_id", "chunk_index", name="uq_chunks_version_chunk_index"),
        sa.UniqueConstraint("document_version_id", "content_hash", name="uq_chunks_version_content_hash"),
    )
    for column in ("project_id", "document_id", "document_version_id", "ingestion_run_id", "qdrant_point_id", "content_hash", "created_at"):
        op.create_index(f"ix_chunks_{column}", "chunks", [column])
    op.create_index("ix_chunks_project_document", "chunks", ["project_id", "document_id"])
    op.create_index("ix_chunks_version_chunk_index", "chunks", ["document_version_id", "chunk_index"])

    op.create_table(
        "embedding_runs",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("embedding_model", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedded_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(_status_check("status", EMBEDDING_STATUSES), name="ck_embedding_runs_status"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_version_id", "embedding_model", name="uq_embedding_runs_version_model"),
    )
    for column in ("project_id", "document_version_id", "embedding_model", "status", "created_at"):
        op.create_index(f"ix_embedding_runs_{column}", "embedding_runs", [column])

    op.create_table(
        "query_logs",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("normalized_question_hash", sa.String(), nullable=True),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("route", sa.String(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("groundedness_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("project_id", "user_id", "normalized_question_hash", "created_at"):
        op.create_index(f"ix_query_logs_{column}", "query_logs", [column])
    op.create_index("ix_query_logs_project_created_at", "query_logs", ["project_id", "created_at"])

    op.create_table(
        "retrieval_logs",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("query_log_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("qdrant_score", sa.Float(), nullable=True),
        sa.Column("rerank_score", sa.Float(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("retrieval_strategy", sa.String(), nullable=True),
        sa.Column("used_in_answer", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["query_log_id"], ["query_logs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("query_log_id", "chunk_id", "rank"):
        op.create_index(f"ix_retrieval_logs_{column}", "retrieval_logs", [column])
    op.create_index("ix_retrieval_logs_query_rank", "retrieval_logs", ["query_log_id", "rank"])


def downgrade() -> None:
    op.drop_table("retrieval_logs")
    op.drop_table("query_logs")
    op.drop_table("embedding_runs")
    op.drop_table("chunks")
    op.drop_table("ingestion_runs")
    op.drop_constraint("fk_documents_current_version_id_document_versions", "documents", type_="foreignkey")
    op.drop_table("document_versions")
    op.drop_table("documents")
    op.drop_table("projects")
    op.drop_table("users")
    op.drop_table("organizations")
