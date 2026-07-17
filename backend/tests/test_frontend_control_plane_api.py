from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.api.query import query_history, query_trace
from app.models import Document, DocumentVersion, IngestionRun
from app.repositories.ingestion_runs import retry_failed_ingestion_run


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _RowsResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FrontendControlPlaneApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_query_history_requires_owned_project_and_returns_durable_answers(self):
        project = SimpleNamespace(id="project-id")
        query_log = SimpleNamespace(
            id="query-id",
            project_id="project-id",
            question="What is RAGForge?",
            answer="A durable RAG control plane.",
            provider="gemini",
            model="gemini-test",
            latency_ms=42,
            cache_hit=False,
            route="rag-stream",
            created_at=datetime(2026, 7, 16),
        )
        db = SimpleNamespace(execute=AsyncMock(return_value=_ScalarResult(project)))

        with patch(
            "app.api.query.query_log_repository.get_project_query_history",
            AsyncMock(return_value=[query_log]),
        ):
            result = await query_history(
                "project-id",
                50,
                db,
                {"user_id": "user-id"},
            )

        self.assertEqual(result[0]["query_log_id"], "query-id")
        self.assertEqual(result[0]["answer"], "A durable RAG control plane.")

    async def test_query_trace_includes_ranked_chunk_and_document_metadata(self):
        query_log = SimpleNamespace(
            id="query-id",
            project_id="project-id",
            question="Where is the evidence?",
            answer="In the indexed document.",
            provider="groq",
            model="model",
            latency_ms=120,
            cache_hit=True,
            route="rag",
            created_at=datetime(2026, 7, 16),
        )
        retrieval = SimpleNamespace(
            id="retrieval-id",
            chunk_id="chunk-id",
            qdrant_score=0.9,
            rerank_score=4.2,
            rank=1,
            retrieval_strategy="hybrid",
            used_in_answer=True,
        )
        chunk = SimpleNamespace(
            document_id="document-id",
            document_version_id="version-id",
            chunk_index=3,
            text="Grounded evidence.",
            section_title="Evidence",
            page_start=2,
            page_end=2,
        )
        document = SimpleNamespace(filename="guide.pdf")
        db = SimpleNamespace(
            execute=AsyncMock(
                side_effect=[
                    _ScalarResult(query_log),
                    _RowsResult([(retrieval, chunk, document)]),
                ]
            )
        )

        result = await query_trace("query-id", db, {"user_id": "user-id"})

        self.assertEqual(result["retrievals"][0]["document_name"], "guide.pdf")
        self.assertEqual(result["retrievals"][0]["rank"], 1)
        self.assertTrue(result["retrievals"][0]["used_in_answer"])

    async def test_query_trace_hides_other_users_queries(self):
        db = SimpleNamespace(execute=AsyncMock(return_value=_ScalarResult(None)))

        with self.assertRaises(HTTPException) as context:
            await query_trace("other-query", db, {"user_id": "user-id"})

        self.assertEqual(context.exception.status_code, 404)

    async def test_failed_ingestion_retry_resets_durable_state(self):
        run = SimpleNamespace(
            id="run-id",
            document_id="document-id",
            document_version_id="version-id",
            status="failed",
            started_at=datetime(2026, 7, 16),
            finished_at=datetime(2026, 7, 16),
            error_message="No indexable text",
            airflow_dag_run_id="dag-id",
        )
        document = SimpleNamespace(status="failed")
        version = SimpleNamespace(
            status="failed",
            error_message="No indexable text",
            silver_path=None,
            gold_path=None,
        )

        async def get(model, identifier):
            if model is IngestionRun and identifier == "run-id":
                return run
            if model is Document and identifier == "document-id":
                return document
            if model is DocumentVersion and identifier == "version-id":
                return version
            return None

        db = SimpleNamespace(get=AsyncMock(side_effect=get), flush=AsyncMock())

        result = await retry_failed_ingestion_run(db, "run-id")

        self.assertIs(result, run)
        self.assertEqual(run.status, "queued")
        self.assertIsNone(run.error_message)
        self.assertIsNone(run.airflow_dag_run_id)
        self.assertEqual(document.status, "landed")
        self.assertEqual(version.status, "landed")
        db.flush.assert_awaited_once()

    async def test_non_failed_ingestion_cannot_be_retried(self):
        run = SimpleNamespace(status="indexed")
        db = SimpleNamespace(get=AsyncMock(return_value=run))

        with self.assertRaisesRegex(ValueError, "Only failed ingestion runs"):
            await retry_failed_ingestion_run(db, "run-id")


if __name__ == "__main__":
    unittest.main()
