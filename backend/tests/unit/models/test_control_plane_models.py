import unittest

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from app.core.db import Base
from app.models import (
    Chunk,
    Document,
    EmbeddingRun,
    IngestionRun,
    QueryLog,
)


class ControlPlaneModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_mappers()

    def test_tasks_4_through_9_tables_are_registered(self):
        self.assertTrue(
            {
                "ingestion_runs",
                "chunks",
                "embedding_runs",
                "query_logs",
                "retrieval_logs",
            }.issubset(Base.metadata.tables)
        )

    def test_current_version_foreign_key_targets_document_versions(self):
        foreign_keys = list(Document.__table__.c.current_version_id.foreign_keys)
        self.assertEqual(len(foreign_keys), 1)
        self.assertEqual(foreign_keys[0].target_fullname, "document_versions.id")
        self.assertEqual(foreign_keys[0].ondelete, "SET NULL")

    def test_query_log_persists_streamed_final_answer(self):
        self.assertIn("answer", QueryLog.__table__.columns)
        self.assertTrue(QueryLog.__table__.c.answer.nullable)

    def test_invalid_lifecycle_statuses_are_rejected_by_models(self):
        cases = (
            (Document, "not-a-document-status"),
            (IngestionRun, "not-an-ingestion-status"),
            (EmbeddingRun, "not-an-embedding-status"),
        )
        for model, status in cases:
            with self.subTest(model=model.__name__):
                with self.assertRaises(ValueError):
                    model(status=status)

    def test_lifecycle_statuses_have_database_check_constraints(self):
        for model in (Document, IngestionRun, EmbeddingRun):
            with self.subTest(model=model.__name__):
                checks = [
                    constraint
                    for constraint in model.__table__.constraints
                    if isinstance(constraint, CheckConstraint)
                ]
                self.assertEqual(len(checks), 1)

    def test_embedding_run_tracks_model_loading_and_retrying(self):
        self.assertEqual(EmbeddingRun(status="loading_model").status, "loading_model")
        self.assertEqual(EmbeddingRun(status="retrying").status, "retrying")

    def test_chunk_uniqueness_constraints_are_present(self):
        unique_columns = {
            tuple(constraint.columns.keys())
            for constraint in Chunk.__table__.constraints
            if isinstance(constraint, UniqueConstraint)
        }
        self.assertIn(("qdrant_point_id",), unique_columns)
        self.assertIn(("document_version_id", "chunk_index"), unique_columns)
        self.assertNotIn(("document_version_id", "content_hash"), unique_columns)

    def test_task_11_required_indexes_are_present(self):
        expected = {
            "documents": {
                ("project_id",),
                ("current_version_id",),
                ("status",),
                ("created_by",),
                ("created_at",),
            },
            "document_versions": {
                ("document_id",),
                ("status",),
                ("content_hash",),
                ("created_at",),
            },
            "ingestion_runs": {
                ("project_id",),
                ("document_id",),
                ("document_version_id",),
                ("status",),
                ("created_at",),
            },
            "chunks": {
                ("project_id",),
                ("document_id",),
                ("document_version_id",),
                ("qdrant_point_id",),
                ("content_hash",),
                ("created_at",),
                ("project_id", "document_id"),
                ("document_version_id", "chunk_index"),
            },
            "query_logs": {
                ("project_id",),
                ("user_id",),
                ("normalized_question_hash",),
                ("created_at",),
                ("project_id", "created_at"),
            },
            "retrieval_logs": {
                ("query_log_id",),
                ("chunk_id",),
                ("rank",),
                ("query_log_id", "rank"),
            },
        }
        for table_name, required_columns in expected.items():
            with self.subTest(table=table_name):
                actual = {
                    tuple(index.columns.keys())
                    for index in Base.metadata.tables[table_name].indexes
                }
                self.assertTrue(required_columns.issubset(actual))


if __name__ == "__main__":
    unittest.main()
