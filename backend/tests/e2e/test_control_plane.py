"""Task 26 full-stack tests executed inside the E2E Compose environment."""

from __future__ import annotations

import unittest

from sqlalchemy import func, select

from app.models import Document
from tests.e2e.helpers import (
    INGESTION_RANK,
    E2EHarness,
    representative_document,
    unique_name,
)
from tests.e2e.provider_stub import ANSWER


class FullControlPlaneE2ETests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.harness = E2EHarness()
        await self.harness.set_provider_failure(False)

    async def asyncTearDown(self) -> None:
        try:
            await self.harness.set_provider_failure(False)
        finally:
            await self.harness.close()

    async def _indexed_project(self, prefix: str):
        identity = await self.harness.create_identity(prefix)
        project = await self.harness.create_project(identity, prefix)
        marker = unique_name(f"{prefix}-lineage").replace("-", "_")
        upload = await self.harness.upload(
            identity,
            project["project_id"],
            filename=f"{marker}.txt",
            content=representative_document(marker),
        )
        status = await self.harness.wait_for_ingestion(
            identity,
            upload["ingestion_run_id"],
            expected="indexed",
        )
        return identity, project, marker, upload, status

    async def test_upload_to_answer_and_cross_system_lineage(self):
        identity = await self.harness.create_identity("happy")
        project = await self.harness.create_project(identity, "happy")
        marker = unique_name("task26_marker").replace("-", "_")
        upload = await self.harness.upload(
            identity,
            project["project_id"],
            filename=f"{marker}.txt",
            content=representative_document(marker),
        )

        initial_graph = await self.harness.ingestion_graph(upload["ingestion_run_id"])
        self.assertEqual(initial_graph["version"].bronze_path.split("/", 1)[0], "bronze")
        self.assertEqual(initial_graph["run"].document_version_id, upload["document_version_id"])
        self.assertTrue(self.harness.read_object(initial_graph["version"].bronze_path))

        ingestion_events = await self.harness.collect_ingestion_events(
            identity,
            upload["ingestion_run_id"],
        )
        statuses = [
            event["status"]
            for event in ingestion_events
            if event.get("status") in INGESTION_RANK
        ]
        self.assertTrue(statuses, ingestion_events)
        self.assertEqual(statuses[-1], "indexed")
        self.assertEqual(
            [INGESTION_RANK[status] for status in statuses],
            sorted({INGESTION_RANK[status] for status in statuses}),
        )

        final_status = await self.harness.wait_for_ingestion(
            identity,
            upload["ingestion_run_id"],
            expected="indexed",
        )
        self.assertEqual(
            final_status["progress"],
            {"bronze": True, "silver": True, "gold": True, "qdrant": True},
        )

        graph = await self.harness.ingestion_graph(upload["ingestion_run_id"])
        run = graph["run"]
        document = graph["document"]
        version = graph["version"]
        chunks = graph["chunks"]
        self.assertEqual(run.status, "indexed")
        self.assertIsNotNone(run.started_at)
        self.assertIsNotNone(run.finished_at)
        self.assertLessEqual(run.started_at, run.finished_at)
        self.assertEqual(document.status, "indexed")
        self.assertEqual(document.current_version_id, version.id)
        self.assertEqual(version.status, "indexed")
        self.assertTrue(version.silver_path.startswith("silver/"))
        self.assertTrue(version.gold_path.startswith("gold/"))
        self.assertIsNotNone(run.airflow_dag_run_id)
        await self.harness.wait_for_airflow_success(run.airflow_dag_run_id)

        silver_rows = self.harness.parquet_rows(version.silver_path)
        gold_rows = self.harness.parquet_rows(version.gold_path)
        self.assertGreater(len(silver_rows), 0)
        self.assertEqual(len(silver_rows), len(gold_rows))
        self.assertEqual(len(gold_rows), len(chunks))
        self.assertEqual(
            [row["chunk_index"] for row in gold_rows],
            [chunk.chunk_index for chunk in chunks],
        )

        points = self.harness.qdrant_points(project["collection"], version.id)
        self.assertEqual(len(points), len(chunks))
        self.assertEqual(
            {str(point.id) for point in points},
            {chunk.qdrant_point_id for chunk in chunks},
        )
        for point in points:
            payload = point.payload
            self.assertEqual(payload["project_id"], project["project_id"])
            self.assertEqual(payload["document_id"], document.id)
            self.assertEqual(payload["document_version_id"], version.id)
            self.assertIn(payload["chunk_id"], {chunk.id for chunk in chunks})
            self.assertEqual(
                payload["lineage_id"],
                f"{version.id}:{payload['chunk_index']}",
            )

        question = f"What storage guarantees are described by {marker}?"
        query_response = await self.harness.api.post(
            "/rag/query",
            headers=identity.headers,
            json={
                "question": question,
                "project_id": project["project_id"],
                "provider": "gemini",
                "include_context": True,
            },
        )
        query_response.raise_for_status()
        query_payload = query_response.json()
        self.assertEqual(query_payload["answer"], ANSWER)
        self.assertFalse(query_payload["cache_hit"])
        self.assertTrue(query_payload["retrieved_chunks"])
        await self._assert_query_lineage(
            query_payload["query_log_id"],
            expected_answer=ANSWER,
            expected_route="rag",
            expected_version_id=version.id,
        )

        stream_question = f"Explain the complete control plane for {marker}."
        query_events = await self.harness.stream_query(
            identity,
            {
                "question": stream_question,
                "project_id": project["project_id"],
                "provider": "gemini",
                "include_context": True,
            },
        )
        event_names = [event["event"] for event in query_events]
        expected_order = [
            "query.received",
            "query.embedding",
            "query.retrieving",
            "query.reranking",
            "query.generating",
        ]
        positions = [event_names.index(name) for name in expected_order]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(event_names[-1], "query.completed")
        streamed_answer = "".join(
            event["text"]
            for event in query_events
            if event["event"] == "query.token"
        )
        self.assertEqual(streamed_answer, ANSWER)
        completed = query_events[-1]
        await self._assert_query_lineage(
            completed["query_log_id"],
            expected_answer=ANSWER,
            expected_route="rag-stream",
            expected_version_id=version.id,
        )

        cached_response = await self.harness.api.post(
            "/rag/query",
            headers=identity.headers,
            json={
                "question": question,
                "project_id": project["project_id"],
                "provider": "gemini",
            },
        )
        cached_response.raise_for_status()
        self.assertTrue(cached_response.json()["cache_hit"])
        cached_graph = await self.harness.query_graph(
            cached_response.json()["query_log_id"]
        )
        self.assertTrue(cached_graph["query_log"].cache_hit)
        self.assertTrue(
            all(
                row.retrieval_strategy.startswith("cache:")
                for row in cached_graph["retrievals"]
            )
        )

    async def _assert_query_lineage(
        self,
        query_log_id: str,
        *,
        expected_answer: str,
        expected_route: str,
        expected_version_id: str,
    ) -> None:
        graph = await self.harness.query_graph(query_log_id)
        query_log = graph["query_log"]
        retrievals = graph["retrievals"]
        chunks = graph["chunks"]
        self.assertIsNotNone(query_log)
        self.assertEqual(query_log.answer, expected_answer)
        self.assertEqual(query_log.route, expected_route)
        self.assertIsNotNone(query_log.latency_ms)
        self.assertGreater(len(retrievals), 0)
        self.assertEqual(
            [row.rank for row in retrievals],
            list(range(1, len(retrievals) + 1)),
        )
        self.assertTrue(all(row.used_in_answer for row in retrievals))
        for retrieval in retrievals:
            self.assertIn(retrieval.chunk_id, chunks)
            self.assertEqual(
                chunks[retrieval.chunk_id].document_version_id,
                expected_version_id,
            )

    async def test_redis_outage_recovers_from_postgres(self):
        identity = await self.harness.create_identity("redis-down")
        project = await self.harness.create_project(identity, "redis-down")
        marker = unique_name("redis_recovery").replace("-", "_")
        upload = await self.harness.upload(
            identity,
            project["project_id"],
            filename=f"{marker}.txt",
            content=representative_document(marker),
        )
        events = await self.harness.collect_ingestion_events(
            identity,
            upload["ingestion_run_id"],
        )
        self.assertEqual(events[-1]["status"], "indexed")
        ranks = [
            INGESTION_RANK[event["status"]]
            for event in events
            if event.get("status") in INGESTION_RANK
        ]
        self.assertEqual(ranks, sorted(set(ranks)))

        question = f"What survives Redis loss for {marker}?"
        response = await self.harness.api.post(
            "/rag/query",
            headers=identity.headers,
            json={
                "question": question,
                "project_id": project["project_id"],
                "provider": "gemini",
            },
        )
        response.raise_for_status()
        payload = response.json()
        self.assertEqual(payload["answer"], ANSWER)
        self.assertFalse(payload["cache_hit"])
        graph = await self.harness.query_graph(payload["query_log_id"])
        self.assertEqual(graph["query_log"].answer, ANSWER)
        self.assertGreater(len(graph["retrievals"]), 0)

    async def test_pipeline_failure_is_durable(self):
        identity = await self.harness.create_identity("pipeline-failure")
        project = await self.harness.create_project(identity, "pipeline-failure")
        upload = await self.harness.upload(
            identity,
            project["project_id"],
            filename=f"{unique_name('empty')}.txt",
            content=b" \n\t ",
        )
        status = await self.harness.wait_for_ingestion(
            identity,
            upload["ingestion_run_id"],
            expected="failed",
        )
        self.assertIn("No indexable text", status["error_message"])
        graph = await self.harness.ingestion_graph(upload["ingestion_run_id"])
        self.assertEqual(graph["run"].status, "failed")
        self.assertIsNotNone(graph["run"].finished_at)
        self.assertEqual(graph["document"].status, "failed")
        self.assertEqual(graph["version"].status, "failed")
        self.assertIsNone(graph["version"].silver_path)
        self.assertIsNone(graph["version"].gold_path)
        self.assertEqual(graph["chunks"], [])

    async def test_provider_failure_preserves_query_and_retrieval_logs(self):
        identity, project, marker, _upload, _status = await self._indexed_project(
            "provider-failure"
        )
        question = f"Force a provider failure after retrieving {marker}."
        await self.harness.set_provider_failure(True)
        try:
            response = await self.harness.api.post(
                "/rag/query",
                headers=identity.headers,
                json={
                    "question": question,
                    "project_id": project["project_id"],
                    "provider": "gemini",
                },
            )
            self.assertGreaterEqual(response.status_code, 500, response.text)
        finally:
            await self.harness.set_provider_failure(False)

        query_log = await self.harness.latest_query_for_question(
            project["project_id"],
            question,
        )
        self.assertIsNotNone(query_log)
        self.assertIsNone(query_log.answer)
        graph = await self.harness.query_graph(query_log.id)
        self.assertGreater(len(graph["retrievals"]), 0)
        self.assertTrue(all(not row.used_in_answer for row in graph["retrievals"]))

    async def test_tenant_isolation_for_runs_documents_and_queries(self):
        owner = await self.harness.create_identity("tenant-owner")
        attacker = await self.harness.create_identity("tenant-attacker")
        project = await self.harness.create_project(owner, "tenant-owner")
        marker = unique_name("tenant_private").replace("-", "_")
        upload = await self.harness.upload(
            owner,
            project["project_id"],
            filename=f"{marker}.txt",
            content=representative_document(marker),
        )

        run_response = await self.harness.api.get(
            f"/ingest/runs/{upload['ingestion_run_id']}",
            headers=attacker.headers,
        )
        self.assertEqual(run_response.status_code, 404)

        event_response = await self.harness.api.get(
            f"/ingest/runs/{upload['ingestion_run_id']}/events",
            headers=attacker.headers,
        )
        self.assertEqual(event_response.status_code, 404)

        document_response = await self.harness.api.get(
            f"/documents/{upload['document_id']}",
            headers=attacker.headers,
        )
        self.assertEqual(document_response.status_code, 404)

        query_response = await self.harness.api.post(
            "/rag/query",
            headers=attacker.headers,
            json={
                "question": f"Reveal {marker}",
                "project_id": project["project_id"],
                "provider": "gemini",
            },
        )
        self.assertEqual(query_response.status_code, 403)

        upload_response = await self.harness.api.post(
            "/ingest/file",
            headers=attacker.headers,
            data={"project_id": project["project_id"], "chunker": "paragraph"},
            files={"file": ("attack.txt", representative_document("attack"), "text/plain")},
        )
        self.assertEqual(upload_response.status_code, 403)

        async with self.harness.sessions() as db:
            document_count = await db.scalar(
                select(func.count())
                .select_from(Document)
                .where(Document.project_id == project["project_id"])
            )
            self.assertEqual(document_count, 1)


if __name__ == "__main__":
    unittest.main()
