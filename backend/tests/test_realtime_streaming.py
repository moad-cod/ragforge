import asyncio
import json
import os
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException

from app.api.ingest import stream_ingestion_run_events
from app.api.internal_pipeline import PipelineStatusUpdate, update_ingestion_run
from app.api.query import QueryRequest, _execute_query, stream_query
from app.services.event_stream import (
    ReplayResult,
    StreamEvent,
    format_sse,
    publish_ingestion_event,
    replay_ingestion_events,
)
from app.services.retrieval.types import RetrievalHit
from app.core.config import settings
import app.services.event_stream as event_stream_module


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Request:
    def __init__(self, disconnected: bool = False):
        self.is_disconnected = AsyncMock(return_value=disconnected)


class _SessionContext:
    def __init__(self, session=None):
        self.session = session or SimpleNamespace()

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_args):
        return None


def _event_payload(message: str) -> dict:
    data_line = next(line for line in message.splitlines() if line.startswith("data: "))
    return json.loads(data_line.removeprefix("data: "))


def _stream_chunk(text: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text))]
    )


async def _inline_to_thread(function, /, *args, **kwargs):
    return function(*args, **kwargs)


class EventStreamServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_publish_and_replay_preserve_monotonic_ids(self):
        client = SimpleNamespace(
            eval=AsyncMock(side_effect=[1, 2]),
            xadd=AsyncMock(side_effect=["1000-0", "1001-0"]),
            expire=AsyncMock(),
            xrange=AsyncMock(),
        )
        with patch("app.services.event_stream._client", return_value=client):
            landed = await publish_ingestion_event("run-1", "landed")
            queued = await publish_ingestion_event("run-1", "queued")
            client.xrange.return_value = [
                (
                    queued.id,
                    {
                        "event": queued.event,
                        "sequence": str(queued.sequence),
                        "timestamp": queued.timestamp,
                        "data": json.dumps(queued.data),
                    },
                )
            ]
            replay = await replay_ingestion_events("run-1", landed.id)

        self.assertLess(landed.sequence, queued.sequence)
        self.assertTrue(replay.available)
        self.assertEqual([event.id for event in replay.events], [queued.id])

    async def test_redis_publish_failure_returns_durable_event(self):
        client = SimpleNamespace(eval=AsyncMock(side_effect=ConnectionError("redis down")))
        with (
            patch("app.services.event_stream._client", return_value=client),
            self.assertLogs("app.services.event_stream", level="WARNING"),
        ):
            event = await publish_ingestion_event("run-1", "running")

        self.assertEqual(event.id, "durable-3-running")
        self.assertEqual(event.data["status"], "running")

    def test_sse_frame_contains_id_event_sequence_and_json_data(self):
        event = StreamEvent(
            id="10-0",
            event="ingestion.running",
            sequence=3,
            timestamp="2026-07-13T10:00:00Z",
            data={"status": "running"},
        )
        frame = format_sse(event)
        self.assertIn("id: 10-0\n", frame)
        self.assertIn("event: ingestion.running\n", frame)
        self.assertEqual(_event_payload(frame)["sequence"], 3)


@unittest.skipUnless(os.getenv("RUN_REDIS_TESTS") == "1", "set RUN_REDIS_TESTS=1 for Redis integration")
class RedisEventIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.redis_url = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/15")
        self.settings_patch = patch.object(settings, "REDIS_URL", self.redis_url)
        self.settings_patch.start()
        event_stream_module._redis = None
        self.run_id = f"test-{uuid.uuid4()}"

    async def asyncTearDown(self):
        client = event_stream_module._client()
        if client is not None:
            await client.delete(
                f"ragforge:events:ingestion:{self.run_id}",
                f"ragforge:events:ingestion:{self.run_id}:sequence",
            )
            await client.aclose()
        event_stream_module._redis = None
        self.settings_patch.stop()

    async def test_real_redis_replays_after_last_event_id(self):
        landed = await publish_ingestion_event(self.run_id, "landed")
        queued = await publish_ingestion_event(self.run_id, "queued")
        replay = await replay_ingestion_events(self.run_id, landed.id)

        self.assertTrue(replay.available)
        self.assertEqual([event.id for event in replay.events], [queued.id])
        self.assertGreater(queued.sequence, landed.sequence)


class IngestionStreamingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.run = SimpleNamespace(
            id="run-1",
            document_id="document-1",
            document_version_id="version-1",
            status="running",
            airflow_dag_run_id="dag-1",
            error_message=None,
        )
        self.version = SimpleNamespace(
            bronze_path="bronze/file",
            silver_path=None,
            gold_path=None,
        )
        self.db = SimpleNamespace()

    async def test_other_tenant_cannot_subscribe(self):
        with patch(
            "app.api.ingest.ingestion_repository.get_owned_ingestion_run",
            AsyncMock(return_value=None),
        ):
            with self.assertRaises(HTTPException) as context:
                await stream_ingestion_run_events(
                    _Request(),
                    "run-1",
                    None,
                    self.db,
                    {"user_id": "other-user"},
                )
        self.assertEqual(context.exception.status_code, 404)

    async def test_first_event_is_current_postgres_snapshot(self):
        self.run.status = "indexed"
        with (
            patch(
                "app.api.ingest.ingestion_repository.get_owned_ingestion_run",
                AsyncMock(return_value=self.run),
            ),
            patch(
                "app.api.ingest.version_repository.get_document_version",
                AsyncMock(return_value=self.version),
            ),
        ):
            response = await stream_ingestion_run_events(
                _Request(), "run-1", None, self.db, {"user_id": "owner"}
            )
            frames = [frame async for frame in response.body_iterator]

        self.assertEqual(len(frames), 1)
        payload = _event_payload(frames[0])
        self.assertEqual(payload["event"], "snapshot")
        self.assertEqual(payload["status"], "indexed")
        self.assertTrue(payload["progress"]["qdrant"])

    async def test_reconnect_replays_new_terminal_event_once(self):
        terminal = StreamEvent(
            id="1002-0",
            event="ingestion.completed",
            sequence=6,
            timestamp="2026-07-13T10:00:00Z",
            data={"ingestion_run_id": "run-1", "status": "indexed"},
        )
        with (
            patch(
                "app.api.ingest.ingestion_repository.get_owned_ingestion_run",
                AsyncMock(return_value=self.run),
            ),
            patch(
                "app.api.ingest.version_repository.get_document_version",
                AsyncMock(return_value=self.version),
            ),
            patch(
                "app.api.ingest.replay_ingestion_events",
                AsyncMock(return_value=ReplayResult([terminal, terminal], True)),
            ),
        ):
            response = await stream_ingestion_run_events(
                _Request(), "run-1", "1001-0", self.db, {"user_id": "owner"}
            )
            frames = [frame async for frame in response.body_iterator]

        events = [_event_payload(frame)["event"] for frame in frames]
        self.assertEqual(events, ["snapshot", "ingestion.completed"])

    async def test_failed_ingestion_emits_one_terminal_failure(self):
        failed = StreamEvent(
            id="1002-0",
            event="ingestion.failed",
            sequence=7,
            timestamp="2026-07-13T10:00:00Z",
            data={"ingestion_run_id": "run-1", "status": "failed", "error_message": "boom"},
        )
        with (
            patch(
                "app.api.ingest.ingestion_repository.get_owned_ingestion_run",
                AsyncMock(return_value=self.run),
            ),
            patch(
                "app.api.ingest.version_repository.get_document_version",
                AsyncMock(return_value=self.version),
            ),
            patch(
                "app.api.ingest.replay_ingestion_events",
                AsyncMock(return_value=ReplayResult([failed, failed], True)),
            ),
        ):
            response = await stream_ingestion_run_events(
                _Request(), "run-1", "1001-0", self.db, {"user_id": "owner"}
            )
            frames = [frame async for frame in response.body_iterator]

        terminal = [
            _event_payload(frame)["event"]
            for frame in frames
            if _event_payload(frame)["event"] == "ingestion.failed"
        ]
        self.assertEqual(terminal, ["ingestion.failed"])

    async def test_missing_redis_history_uses_snapshot_and_heartbeat(self):
        stream_db = SimpleNamespace()
        with (
            patch(
                "app.api.ingest.ingestion_repository.get_owned_ingestion_run",
                AsyncMock(return_value=self.run),
            ),
            patch(
                "app.api.ingest.version_repository.get_document_version",
                AsyncMock(return_value=self.version),
            ),
            patch(
                "app.api.ingest.replay_ingestion_events",
                AsyncMock(return_value=ReplayResult([], False)),
            ),
            patch("app.api.ingest.AsyncSessionLocal", return_value=_SessionContext(stream_db)),
            patch(
                "app.api.ingest.ingestion_repository.get_ingestion_run",
                AsyncMock(return_value=self.run),
            ),
            patch.object(__import__("app.api.ingest", fromlist=["settings"]).settings, "SSE_HEARTBEAT_SECONDS", 0),
            patch.object(__import__("app.api.ingest", fromlist=["settings"]).settings, "SSE_POLL_SECONDS", 0),
        ):
            response = await stream_ingestion_run_events(
                _Request(), "run-1", "missing", self.db, {"user_id": "owner"}
            )
            iterator = response.body_iterator
            snapshot = await anext(iterator)
            heartbeat = await anext(iterator)
            await iterator.aclose()

        self.assertEqual(_event_payload(snapshot)["event"], "snapshot")
        self.assertTrue(heartbeat.startswith(": heartbeat"))

    async def test_pipeline_transition_publishes_after_durable_commit(self):
        self.run.project_id = "project-1"
        self.run.created_at = "2026-07-13T10:00:00Z"
        self.run.started_at = "2026-07-13T10:00:00Z"
        self.run.finished_at = None
        db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
        with (
            patch(
                "app.api.internal_pipeline.ingestion_repository.update_ingestion_status",
                AsyncMock(return_value=self.run),
            ),
            patch(
                "app.api.internal_pipeline.publish_ingestion_event",
                AsyncMock(),
            ) as publish_event,
        ):
            response = await update_ingestion_run(
                "run-1",
                PipelineStatusUpdate(status="running"),
                db,
            )

        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(self.run)
        publish_event.assert_awaited_once()
        self.assertEqual(response["status"], "running")


class QueryStreamingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.project = SimpleNamespace(id="project-1", collection="project_collection")
        self.db = SimpleNamespace(
            execute=AsyncMock(return_value=_ScalarResult(self.project)),
            commit=AsyncMock(),
            rollback=AsyncMock(),
        )
        self.request = QueryRequest(
            question="What is streamed?",
            project_id="project-1",
            provider="gemini",
        )
        self.hit = RetrievalHit(
            text="A streamed answer uses tokens.",
            chunk_id="00000000-0000-0000-0000-000000000001",
            qdrant_point_id="00000000-0000-0000-0000-000000000002",
            qdrant_score=0.9,
            rerank_score=4.0,
            rank=1,
            retrieval_strategy="hybrid",
        )

    async def test_query_events_are_ordered_and_tokens_match_persisted_answer(self):
        emitted = []

        async def emit(event, data):
            emitted.append((event, data))

        completion = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=Mock(return_value=iter([_stream_chunk("Hello "), _stream_chunk("world")]))
                )
            )
        )
        query_log = SimpleNamespace(id="query-log-1")
        finish = AsyncMock(return_value=query_log)
        with (
            patch("app.api.query.get_cached_query", AsyncMock(return_value=None)),
            patch("app.api.query.asyncio.to_thread", new=_inline_to_thread),
            patch("app.api.query.set_cached_query", AsyncMock()),
            patch("app.api.query.embed_query", Mock(return_value=[0.1, 0.2])),
            patch("app.api.query.search", Mock(return_value=[self.hit])),
            patch("app.api.query.get_llm_client", return_value=(completion, "model")),
            patch(
                "app.api.query.query_log_repository.create_query_log",
                AsyncMock(return_value=query_log),
            ),
            patch("app.api.query.query_log_repository.finish_query_log", finish),
            patch(
                "app.api.query.retrieval_log_repository.bulk_insert_retrieval_logs",
                AsyncMock(return_value=[SimpleNamespace(used_in_answer=False)]),
            ),
            patch(
                "app.api.query.retrieval_log_repository.mark_retrieval_logs_used",
                AsyncMock(),
            ),
        ):
            result = await _execute_query(
                self.request,
                self.db,
                "user-1",
                emit=emit,
                stream_tokens=True,
                route="rag-stream",
            )

        event_types = [event for event, _data in emitted]
        self.assertEqual(
            event_types,
            [
                "query.received",
                "query.embedding",
                "query.retrieving",
                "query.reranking",
                "query.generating",
                "query.token",
                "query.token",
                "query.completed",
            ],
        )
        token_answer = "".join(data["text"] for event, data in emitted if event == "query.token")
        self.assertEqual(token_answer, "Hello world")
        self.assertEqual(result["answer"], token_answer)
        self.assertEqual(finish.await_args.kwargs["answer"], token_answer)
        self.assertEqual(finish.await_args.kwargs["route"], "rag-stream")

    async def test_failed_query_emits_one_terminal_failure_and_commits_log(self):
        emitted = []

        async def emit(event, data):
            emitted.append((event, data))

        query_log = SimpleNamespace(id="query-log-1")
        with (
            patch("app.api.query.get_cached_query", AsyncMock(return_value=None)),
            patch("app.api.query.asyncio.to_thread", new=_inline_to_thread),
            patch("app.api.query.embed_query", Mock(return_value=[0.1, 0.2])),
            patch("app.api.query.search", Mock(return_value=[self.hit])),
            patch("app.api.query.get_llm_client", side_effect=HTTPException(503, "provider down")),
            patch(
                "app.api.query.query_log_repository.create_query_log",
                AsyncMock(return_value=query_log),
            ),
            patch(
                "app.api.query.query_log_repository.finish_query_log",
                AsyncMock(return_value=query_log),
            ),
            patch(
                "app.api.query.retrieval_log_repository.bulk_insert_retrieval_logs",
                AsyncMock(return_value=[SimpleNamespace(used_in_answer=False)]),
            ),
        ):
            with self.assertRaises(HTTPException):
                await _execute_query(
                    self.request,
                    self.db,
                    "user-1",
                    emit=emit,
                    stream_tokens=True,
                )

        terminal = [event for event, _data in emitted if event in {"query.completed", "query.failed"}]
        self.assertEqual(terminal, ["query.failed"])
        self.db.commit.assert_awaited_once()

    async def test_client_disconnect_does_not_cancel_query_worker(self):
        completed = asyncio.Event()
        query_log = SimpleNamespace(id="query-log-1")

        async def finish(*_args, **_kwargs):
            completed.set()
            return query_log

        with (
            patch("app.api.query._authorize_query", AsyncMock(return_value=self.project)),
            patch(
                "app.api.query.get_cached_query",
                AsyncMock(
                    return_value={
                        "answer": "Durable cached answer",
                        "hits": [self.hit.to_cache_dict()],
                    }
                ),
            ),
            patch(
                "app.api.query.query_log_repository.create_query_log",
                AsyncMock(return_value=query_log),
            ),
            patch(
                "app.api.query.query_log_repository.finish_query_log",
                AsyncMock(side_effect=finish),
            ) as finish_log,
            patch(
                "app.api.query.retrieval_log_repository.bulk_insert_retrieval_logs",
                AsyncMock(return_value=[]),
            ) as insert_retrievals,
            patch("app.api.query.AsyncSessionLocal", return_value=_SessionContext(self.db)),
        ):
            response = await stream_query(
                self.request,
                _Request(disconnected=True),
                self.db,
                {"user_id": "user-1"},
            )
            frames = [frame async for frame in response.body_iterator]
            await asyncio.wait_for(completed.wait(), timeout=1)

        self.assertEqual(frames, [])
        self.assertEqual(finish_log.await_args.kwargs["answer"], "Durable cached answer")
        insert_retrievals.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
