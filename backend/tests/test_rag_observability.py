from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException
from qdrant_client.models import SparseVector

from app.api.query import QueryRequest, query
from app.services.query_cache import cache_key, get_cached_query, set_cached_query
from app.services.query_observability import normalize_question, normalized_question_hash
from app.services.retrieval.hybrid import hybrid_search
from app.services.retrieval.types import RetrievalHit
from app.services.retriever import search


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class RagObservabilityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.project = SimpleNamespace(id="project-id", collection="project_collection")
        self.db = SimpleNamespace(
            execute=AsyncMock(return_value=_ScalarResult(self.project)),
            commit=AsyncMock(),
            rollback=AsyncMock(),
        )
        self.request = QueryRequest(
            question="  What   is RAGForge?  ",
            project_id="project-id",
            provider="gemini",
            include_context=True,
        )
        self.query_log = SimpleNamespace(id="query-log-id")
        self.hit = RetrievalHit(
            text="RAGForge is a retrieval platform.",
            chunk_id="00000000-0000-0000-0000-000000000001",
            qdrant_point_id="00000000-0000-0000-0000-000000000002",
            qdrant_score=0.82,
            rerank_score=4.2,
            rank=1,
            retrieval_strategy="hybrid_rrf_cross_encoder",
        )

    def test_question_normalization_is_stable(self):
        self.assertEqual(normalize_question("  What   IS\nRAG? "), "what is rag?")
        self.assertEqual(
            normalized_question_hash("What IS RAG?"),
            normalized_question_hash("  what  is rag? "),
        )

    def test_cache_key_is_scoped_to_query_dimensions(self):
        base = {
            "project_id": "project-id",
            "normalized_question_hash": normalized_question_hash("question"),
            "provider": "gemini",
            "model": "model-a",
            "document_id": None,
            "use_parent_context": False,
        }
        self.assertEqual(cache_key(**base), cache_key(**base))
        self.assertNotEqual(cache_key(**base), cache_key(**{**base, "project_id": "other"}))
        self.assertNotEqual(cache_key(**base), cache_key(**{**base, "document_id": "document"}))
        self.assertNotEqual(
            cache_key(**base),
            cache_key(**{**base, "use_parent_context": True}),
        )

    async def test_redis_failure_does_not_replace_durable_query_path(self):
        unavailable = SimpleNamespace(
            get=AsyncMock(side_effect=ConnectionError("redis unavailable")),
            setex=AsyncMock(side_effect=ConnectionError("redis unavailable")),
        )
        with (
            patch("app.services.query_cache._client", return_value=unavailable),
            self.assertLogs("app.services.query_cache", level="WARNING") as logs,
        ):
            self.assertIsNone(await get_cached_query("query-key"))
            await set_cached_query("query-key", {"answer": "still durable"})

        unavailable.get.assert_awaited_once_with("query-key")
        unavailable.setex.assert_awaited_once()
        self.assertEqual(len(logs.output), 2)

    async def test_successful_query_logs_query_retrieval_scores_and_usage(self):
        llm_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="A grounded answer."))]
        )
        retrieval_record = SimpleNamespace(used_in_answer=False)

        with (
            patch("app.api.query.get_cached_query", AsyncMock(return_value=None)),
            patch("app.api.query.set_cached_query", AsyncMock()) as set_cache,
            patch(
                "app.api.query.query_log_repository.create_query_log",
                AsyncMock(return_value=self.query_log),
            ) as create_log,
            patch(
                "app.api.query.query_log_repository.finish_query_log",
                AsyncMock(return_value=self.query_log),
            ) as finish_log,
            patch(
                "app.api.query.retrieval_log_repository.bulk_insert_retrieval_logs",
                AsyncMock(return_value=[retrieval_record]),
            ) as insert_retrievals,
            patch(
                "app.api.query.retrieval_log_repository.mark_retrieval_logs_used",
                AsyncMock(),
            ) as mark_used,
            patch(
                "app.api.query.get_llm_client",
                return_value=(
                    SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=Mock()))),
                    "default",
                ),
            ),
            patch(
                "app.api.query.asyncio.to_thread",
                AsyncMock(side_effect=[[0.1, 0.2], [self.hit], llm_response]),
            ),
        ):
            response = await query(self.request, self.db, {"user_id": "user-id"})

        self.assertEqual(response["query_log_id"], "query-log-id")
        self.assertEqual(response["answer"], "A grounded answer.")
        self.assertFalse(response["cache_hit"])
        self.assertEqual(response["retrieved_chunks"], [self.hit.text])
        self.assertEqual(
            create_log.await_args.kwargs["normalized_question_hash"],
            normalized_question_hash(self.request.question),
        )
        self.assertEqual(create_log.await_args.kwargs["provider"], "gemini")
        values = insert_retrievals.await_args.args[1]
        self.assertEqual(values[0]["chunk_id"], self.hit.chunk_id)
        self.assertEqual(values[0]["qdrant_score"], 0.82)
        self.assertEqual(values[0]["rerank_score"], 4.2)
        self.assertEqual(values[0]["rank"], 1)
        self.assertEqual(values[0]["retrieval_strategy"], "hybrid_rrf_cross_encoder")
        mark_used.assert_awaited_once_with(self.db, [retrieval_record])
        self.assertFalse(finish_log.await_args.kwargs["cache_hit"])
        self.assertGreaterEqual(finish_log.await_args.kwargs["latency_ms"], 0)
        self.db.commit.assert_awaited_once()
        set_cache.assert_awaited_once()

    async def test_cache_hit_is_logged_with_cached_retrieval_trace(self):
        cached_hit = self.hit.to_cache_dict()
        with (
            patch(
                "app.api.query.get_cached_query",
                AsyncMock(return_value={"answer": "Cached answer", "hits": [cached_hit]}),
            ),
            patch(
                "app.api.query.query_log_repository.create_query_log",
                AsyncMock(return_value=self.query_log),
            ) as create_log,
            patch(
                "app.api.query.query_log_repository.finish_query_log",
                AsyncMock(return_value=self.query_log),
            ) as finish_log,
            patch(
                "app.api.query.retrieval_log_repository.bulk_insert_retrieval_logs",
                AsyncMock(return_value=[]),
            ) as insert_retrievals,
            patch("app.api.query.asyncio.to_thread", AsyncMock()) as to_thread,
        ):
            response = await query(self.request, self.db, {"user_id": "user-id"})

        self.assertTrue(response["cache_hit"])
        self.assertEqual(response["answer"], "Cached answer")
        self.assertTrue(create_log.await_args.kwargs["cache_hit"])
        self.assertTrue(finish_log.await_args.kwargs["cache_hit"])
        values = insert_retrievals.await_args.args[1]
        self.assertEqual(values[0]["retrieval_strategy"], "cache:hybrid_rrf_cross_encoder")
        self.assertTrue(values[0]["used_in_answer"])
        to_thread.assert_not_awaited()

    async def test_provider_failure_still_commits_query_and_retrieval_logs(self):
        with (
            patch("app.api.query.get_cached_query", AsyncMock(return_value=None)),
            patch(
                "app.api.query.query_log_repository.create_query_log",
                AsyncMock(return_value=self.query_log),
            ),
            patch(
                "app.api.query.query_log_repository.finish_query_log",
                AsyncMock(return_value=self.query_log),
            ) as finish_log,
            patch(
                "app.api.query.retrieval_log_repository.bulk_insert_retrieval_logs",
                AsyncMock(return_value=[SimpleNamespace(used_in_answer=False)]),
            ) as insert_retrievals,
            patch(
                "app.api.query.retrieval_log_repository.mark_retrieval_logs_used",
                AsyncMock(),
            ) as mark_used,
            patch("app.api.query.get_llm_client", side_effect=HTTPException(503, "missing key")),
            patch(
                "app.api.query.asyncio.to_thread",
                AsyncMock(side_effect=[[0.1, 0.2], [self.hit]]),
            ),
        ):
            with self.assertRaises(HTTPException):
                await query(self.request, self.db, {"user_id": "user-id"})

        self.assertEqual(insert_retrievals.await_args.args[1][0]["used_in_answer"], False)
        mark_used.assert_not_awaited()
        finish_log.assert_awaited_once()
        self.db.commit.assert_awaited_once()

    async def test_empty_retrieval_still_logs_query(self):
        with (
            patch("app.api.query.get_cached_query", AsyncMock(return_value=None)),
            patch(
                "app.api.query.query_log_repository.create_query_log",
                AsyncMock(return_value=self.query_log),
            ),
            patch(
                "app.api.query.query_log_repository.finish_query_log",
                AsyncMock(return_value=self.query_log),
            ),
            patch(
                "app.api.query.retrieval_log_repository.bulk_insert_retrieval_logs",
                AsyncMock(return_value=[]),
            ) as insert_retrievals,
            patch(
                "app.api.query.asyncio.to_thread",
                AsyncMock(side_effect=[[0.1, 0.2], []]),
            ),
        ):
            response = await query(self.request, self.db, {"user_id": "user-id"})

        self.assertEqual(response["answer"], "No documents found for this project.")
        self.assertEqual(insert_retrievals.await_args.args[1], [])
        self.db.commit.assert_awaited_once()


class StructuredHybridRetrievalTests(unittest.TestCase):
    def test_hybrid_search_preserves_scores_rank_and_tenant_filter(self):
        points = [
            SimpleNamespace(
                id="point-1",
                score=0.71,
                payload={
                    "text": "First",
                    "project_id": "project-id",
                    "document_version_id": "version-id",
                    "chunk_id": "chunk-1",
                },
            ),
            SimpleNamespace(
                id="point-2",
                score=0.64,
                payload={
                    "text": "Second",
                    "project_id": "project-id",
                    "document_version_id": "version-id",
                    "chunk_id": "chunk-2",
                },
            ),
        ]
        with (
            patch(
                "app.services.retrieval.hybrid.embed_sparse_query",
                return_value=SparseVector(indices=[1], values=[1.0]),
            ),
            patch(
                "app.services.retrieval.hybrid.qdrant.query_points",
                return_value=SimpleNamespace(points=points),
            ) as query_points,
            patch(
                "app.services.retrieval.hybrid.rerank_with_scores",
                return_value=[(1, 3.5), (0, 2.1)],
            ),
        ):
            hits = hybrid_search(
                dense_embedding=[0.1, 0.2],
                query_text="question",
                project_id="project-id",
                collection="collection",
                top_k=2,
            )

        self.assertEqual([hit.chunk_id for hit in hits], ["chunk-2", "chunk-1"])
        self.assertEqual([hit.rank for hit in hits], [1, 2])
        self.assertEqual([hit.qdrant_score for hit in hits], [0.64, 0.71])
        self.assertEqual([hit.rerank_score for hit in hits], [3.5, 2.1])
        query_filter = query_points.call_args.kwargs["query_filter"]
        self.assertEqual(query_filter.must[0].key, "project_id")
        self.assertEqual(query_filter.must[0].match.value, "project-id")

    def test_dense_fallback_returns_structured_hits_and_project_filter(self):
        point = SimpleNamespace(
            id="point-1",
            score=0.55,
            payload={
                "text": "Dense result",
                "document_version_id": "version-id",
                "chunk_id": "chunk-id",
            },
        )
        with patch(
            "app.services.retriever.qdrant.query_points",
            return_value=SimpleNamespace(points=[point]),
        ) as query_points:
            hits = search(
                embedding=[0.1, 0.2],
                project_id="project-id",
                collection="collection",
                query_text="question",
                use_hybrid=False,
            )

        self.assertEqual(hits[0].text, "Dense result")
        self.assertEqual(hits[0].chunk_id, "chunk-id")
        self.assertEqual(hits[0].qdrant_score, 0.55)
        self.assertEqual(hits[0].rank, 1)
        self.assertEqual(hits[0].retrieval_strategy, "dense")
        query_filter = query_points.call_args.kwargs["query_filter"]
        self.assertEqual(query_filter.must[0].key, "project_id")
        self.assertEqual(query_filter.must[0].match.value, "project-id")


if __name__ == "__main__":
    unittest.main()
