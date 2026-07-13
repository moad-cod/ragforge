"""Database introspection checks for the final control-plane schema."""

from dataclasses import dataclass

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine


CORE_TABLES = frozenset(
    {
        "organizations",
        "users",
        "projects",
        "documents",
        "document_versions",
        "ingestion_runs",
        "chunks",
        "embedding_runs",
        "query_logs",
        "retrieval_logs",
    }
)

REQUIRED_FOREIGN_KEYS = frozenset(
    {
        ("users", ("organization_id",), "organizations"),
        ("projects", ("organization_id",), "organizations"),
        ("projects", ("created_by",), "users"),
        ("documents", ("project_id",), "projects"),
        ("documents", ("created_by",), "users"),
        ("documents", ("current_version_id",), "document_versions"),
        ("document_versions", ("document_id",), "documents"),
        ("ingestion_runs", ("project_id",), "projects"),
        ("ingestion_runs", ("document_id",), "documents"),
        ("ingestion_runs", ("document_version_id",), "document_versions"),
        ("ingestion_runs", ("created_by",), "users"),
        ("chunks", ("project_id",), "projects"),
        ("chunks", ("document_id",), "documents"),
        ("chunks", ("document_version_id",), "document_versions"),
        ("chunks", ("ingestion_run_id",), "ingestion_runs"),
        ("embedding_runs", ("project_id",), "projects"),
        ("embedding_runs", ("document_version_id",), "document_versions"),
        ("query_logs", ("project_id",), "projects"),
        ("query_logs", ("user_id",), "users"),
        ("retrieval_logs", ("query_log_id",), "query_logs"),
        ("retrieval_logs", ("chunk_id",), "chunks"),
    }
)

REQUIRED_UNIQUE_CONSTRAINTS = frozenset(
    {
        ("users", "uq_users_email"),
        ("projects", "uq_projects_qdrant_collection"),
        ("document_versions", "uq_document_versions_document_version_number"),
        ("document_versions", "uq_document_versions_document_content_hash"),
        ("chunks", "uq_chunks_qdrant_point_id"),
        ("chunks", "uq_chunks_version_chunk_index"),
        ("chunks", "uq_chunks_version_content_hash"),
        ("embedding_runs", "uq_embedding_runs_version_model"),
    }
)

REQUIRED_CHECK_CONSTRAINTS = frozenset(
    {
        ("documents", "ck_documents_status"),
        ("ingestion_runs", "ck_ingestion_runs_status"),
        ("embedding_runs", "ck_embedding_runs_status"),
    }
)

REQUIRED_INDEXES = frozenset(
    {
        ("documents", "ix_documents_project_id"),
        ("documents", "ix_documents_current_version_id"),
        ("documents", "ix_documents_status"),
        ("document_versions", "ix_document_versions_document_id"),
        ("document_versions", "ix_document_versions_content_hash"),
        ("ingestion_runs", "ix_ingestion_runs_status"),
        ("chunks", "ix_chunks_project_document"),
        ("chunks", "ix_chunks_version_chunk_index"),
        ("chunks", "ix_chunks_qdrant_point_id"),
        ("query_logs", "ix_query_logs_project_created_at"),
        ("query_logs", "ix_query_logs_normalized_question_hash"),
        ("retrieval_logs", "ix_retrieval_logs_query_rank"),
    }
)


@dataclass(frozen=True)
class SchemaValidationReport:
    checks: dict[str, bool]
    missing: dict[str, tuple[str, ...]]

    @property
    def ok(self) -> bool:
        return all(self.checks.values())


def _qualified(items) -> tuple[str, ...]:
    return tuple(sorted(f"{table}.{name}" for table, name in items))


def _inspect_schema(connection) -> SchemaValidationReport:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())

    foreign_keys = set()
    unique_constraints = set()
    check_constraints = set()
    indexes = set()
    for table in CORE_TABLES & tables:
        foreign_keys.update(
            (
                table,
                tuple(foreign_key["constrained_columns"]),
                foreign_key["referred_table"],
            )
            for foreign_key in inspector.get_foreign_keys(table)
        )
        unique_constraints.update(
            (table, constraint["name"])
            for constraint in inspector.get_unique_constraints(table)
            if constraint["name"]
        )
        check_constraints.update(
            (table, constraint["name"])
            for constraint in inspector.get_check_constraints(table)
            if constraint["name"]
        )
        indexes.update(
            (table, index["name"])
            for index in inspector.get_indexes(table)
            if index["name"]
        )

    missing_tables = CORE_TABLES - tables
    missing_foreign_keys = REQUIRED_FOREIGN_KEYS - foreign_keys
    missing_unique = REQUIRED_UNIQUE_CONSTRAINTS - unique_constraints
    missing_checks = REQUIRED_CHECK_CONSTRAINTS - check_constraints
    missing_indexes = REQUIRED_INDEXES - indexes
    missing = {
        "tables": tuple(sorted(missing_tables)),
        "foreign_keys": tuple(
            sorted(
                f"{table}({','.join(columns)})->{referred_table}"
                for table, columns, referred_table in missing_foreign_keys
            )
        ),
        "unique_constraints": _qualified(missing_unique),
        "check_constraints": _qualified(missing_checks),
        "indexes": _qualified(missing_indexes),
    }
    return SchemaValidationReport(
        checks={name: not values for name, values in missing.items()},
        missing=missing,
    )


async def validate_control_plane_schema(engine: AsyncEngine) -> SchemaValidationReport:
    async with engine.connect() as connection:
        return await connection.run_sync(_inspect_schema)
