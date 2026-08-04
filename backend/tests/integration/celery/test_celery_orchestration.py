import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from app.core.config import settings
from app.services.ingestion_orchestrator import ingestion_orchestration_enabled


class _DatabaseContext:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *_args):
        return None


class _Workflow:
    def __init__(self, result_id="celery-workflow-id"):
        self.result_id = result_id

    def apply_async(self):
        return SimpleNamespace(id=self.result_id)


class IngestionOrchestratorTests(unittest.TestCase):
    def test_airflow_enabled_requires_airflow_api_url(self):
        with (
            patch.object(settings, "ORCHESTRATOR", "airflow"),
            patch.object(settings, "AIRFLOW_API_URL", ""),
        ):
            self.assertFalse(ingestion_orchestration_enabled())

        with (
            patch.object(settings, "ORCHESTRATOR", "airflow"),
            patch.object(settings, "AIRFLOW_API_URL", "http://airflow:8080"),
        ):
            self.assertTrue(ingestion_orchestration_enabled())

    def test_celery_enabled_requires_broker_or_eager_mode(self):
        with (
            patch.object(settings, "ORCHESTRATOR", "celery"),
            patch.object(settings, "CELERY_BROKER_URL", ""),
            patch.object(settings, "CELERY_TASK_ALWAYS_EAGER", False),
        ):
            self.assertFalse(ingestion_orchestration_enabled())

        with (
            patch.object(settings, "ORCHESTRATOR", "celery"),
            patch.object(settings, "CELERY_BROKER_URL", "redis://redis:6379/1"),
            patch.object(settings, "CELERY_TASK_ALWAYS_EAGER", False),
        ):
            self.assertTrue(ingestion_orchestration_enabled())

class IngestionDispatchFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_configured_orchestrator_failure_marks_run_failed(self):
        from app.services import ingestion_orchestrator

        db = SimpleNamespace(commit=AsyncMock())

        with (
            patch.object(settings, "ORCHESTRATOR", "celery"),
            patch.object(settings, "CELERY_BROKER_URL", "redis://redis:6379/1"),
            patch.object(settings, "CELERY_TASK_ALWAYS_EAGER", False),
            patch(
                "app.workers.tasks.enqueue_ingestion",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.services.ingestion_orchestrator.AsyncSessionLocal",
                side_effect=lambda: _DatabaseContext(db),
            ),
            patch(
                "app.services.ingestion_orchestrator.mark_ingestion_failed",
                AsyncMock(return_value=SimpleNamespace(id="run-id")),
            ) as mark_failed,
            patch(
                "app.services.ingestion_orchestrator.publish_ingestion_event",
                AsyncMock(),
            ) as publish_event,
        ):
            result = await ingestion_orchestrator.enqueue_ingestion("run-id")

        self.assertIsNone(result)
        mark_failed.assert_awaited_once_with(
            db,
            "run-id",
            ingestion_orchestrator.DISPATCH_FAILURE_MESSAGE,
        )
        db.commit.assert_awaited_once()
        publish_event.assert_awaited_once_with(
            "run-id",
            "failed",
            data={"error_message": ingestion_orchestrator.DISPATCH_FAILURE_MESSAGE},
        )

    async def test_configured_orchestrator_exception_is_marked_failed_and_raised(self):
        from app.services import ingestion_orchestrator

        db = SimpleNamespace(commit=AsyncMock())

        with (
            patch.object(settings, "ORCHESTRATOR", "celery"),
            patch.object(settings, "CELERY_BROKER_URL", "redis://redis:6379/1"),
            patch.object(settings, "CELERY_TASK_ALWAYS_EAGER", False),
            patch(
                "app.workers.tasks.enqueue_ingestion",
                AsyncMock(side_effect=RuntimeError("broker unavailable")),
            ),
            patch(
                "app.services.ingestion_orchestrator.AsyncSessionLocal",
                side_effect=lambda: _DatabaseContext(db),
            ),
            patch(
                "app.services.ingestion_orchestrator.mark_ingestion_failed",
                AsyncMock(return_value=SimpleNamespace(id="run-id")),
            ) as mark_failed,
            patch(
                "app.services.ingestion_orchestrator.publish_ingestion_event",
                AsyncMock(),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "broker unavailable"):
                await ingestion_orchestrator.enqueue_ingestion("run-id")

        mark_failed.assert_awaited_once()
        db.commit.assert_awaited_once()


class CeleryIngestionTests(unittest.IsolatedAsyncioTestCase):
    async def test_enqueue_publishes_workflow_and_marks_run_queued(self):
        from app.workers import tasks as celery_tasks

        db = SimpleNamespace(commit=AsyncMock())

        with (
            patch.object(settings, "CELERY_BROKER_URL", "redis://redis:6379/1"),
            patch.object(settings, "CELERY_TASK_ALWAYS_EAGER", False),
            patch.object(
                celery_tasks,
                "build_ingestion_workflow",
                Mock(return_value=_Workflow()),
            ) as build_workflow,
            patch(
                "app.workers.tasks.AsyncSessionLocal",
                side_effect=lambda: _DatabaseContext(db),
            ),
            patch(
                "app.workers.tasks.update_ingestion_status",
                AsyncMock(),
            ) as update_status,
            patch(
                "app.workers.tasks.publish_ingestion_event",
                AsyncMock(),
            ) as publish_event,
        ):
            result = await celery_tasks.enqueue_ingestion("run-id")

        self.assertEqual(result, "celery-workflow-id")
        build_workflow.assert_called_once_with("run-id")
        self.assertEqual(update_status.await_args.args[1], "run-id")
        self.assertEqual(update_status.await_args.args[2], "queued")
        self.assertEqual(
            update_status.await_args.kwargs["airflow_dag_run_id"],
            "celery-workflow-id",
        )
        db.commit.assert_awaited_once()
        publish_event.assert_awaited_once_with(
            "run-id",
            "queued",
            data={"airflow_dag_run_id": "celery-workflow-id"},
        )

    async def test_enqueue_is_disabled_without_broker_unless_eager(self):
        from app.workers import tasks as celery_tasks

        with (
            patch.object(settings, "CELERY_BROKER_URL", ""),
            patch.object(settings, "CELERY_TASK_ALWAYS_EAGER", False),
            patch.object(celery_tasks, "build_ingestion_workflow") as build_workflow,
        ):
            result = await celery_tasks.enqueue_ingestion("run-id")

        self.assertIsNone(result)
        build_workflow.assert_not_called()


class CeleryEmbeddingRetryTests(unittest.TestCase):
    def test_silver_to_gold_retry_marks_embedding_progress_retrying(self):
        from app.workers import tasks as celery_tasks

        client = Mock()
        client.get_run.return_value = {"embedding_model": "BAAI/bge-small-en-v1.5"}
        task = SimpleNamespace(
            name="ragforge.ingestion.silver_to_gold",
            max_retries=2,
            request=SimpleNamespace(retries=0),
            retry=Mock(side_effect=RuntimeError("retry scheduled")),
        )

        with patch.object(celery_tasks, "RAGForgeControlPlane", return_value=client):
            with self.assertRaisesRegex(RuntimeError, "retry scheduled"):
                celery_tasks._handle_stage_error(task, "run-id", RuntimeError("temporary"))

        client.update_embedding_progress.assert_called_once()
        progress = client.update_embedding_progress.call_args.args[1]
        self.assertEqual(progress["stage"], "retrying")
        self.assertEqual(progress["attempt"], 2)


class SharedIngestionWorkflowTests(unittest.TestCase):
    def test_detect_plan_marks_run_running(self):
        from jobs import ingestion_workflow

        client = Mock()
        client.get_run.return_value = {
            "status": "queued",
            "ingestion_plan": {"profile": "throughput"},
        }

        with patch.object(
            ingestion_workflow,
            "RAGForgeControlPlane",
            return_value=client,
        ):
            result = ingestion_workflow.detect_ingestion_plan("run-id")

        self.assertEqual(
            result,
            {
                "ingestion_run_id": "run-id",
                "ingestion_plan": {"profile": "throughput"},
            },
        )
        client.update_status.assert_called_once_with("run-id", "running")

    def test_stage_boundaries_update_expected_statuses(self):
        from jobs import ingestion_workflow

        client = Mock()
        client.get_run.return_value = {"ingestion_run_id": "run-id"}
        ingestion = {"ingestion_run_id": "run-id", "ingestion_plan": {}}

        with (
            patch.object(
                ingestion_workflow,
                "RAGForgeControlPlane",
                return_value=client,
            ),
            patch.object(
                ingestion_workflow,
                "bronze_to_silver",
                return_value={"artifact_path": "silver/path.parquet"},
            ),
            patch.object(
                ingestion_workflow,
                "silver_to_gold",
                return_value={"artifact_path": "gold/path.parquet"},
            ) as silver_to_gold_mock,
            patch.object(
                ingestion_workflow,
                "gold_chunks",
                return_value=[{"chunk_index": 0, "text": "hello", "dense_vector": [0.1]}],
            ),
        ):
            ingestion_workflow.bronze_to_silver_stage(ingestion)
            ingestion_workflow.silver_to_gold_embed_stage(ingestion)
            ingestion_workflow.upsert_qdrant_stage(ingestion)
            ingestion_workflow.finalize_ingestion_stage(ingestion)

        client.update_status.assert_any_call(
            "run-id",
            "silver_completed",
            silver_path="silver/path.parquet",
        )
        client.update_status.assert_any_call(
            "run-id",
            "gold_completed",
            gold_path="gold/path.parquet",
        )
        client.index_chunks.assert_called_once()
        silver_to_gold_mock.call_args.kwargs["progress_callback"](
            {"stage": "running", "embedding_model": "model", "total_chunks": 1, "embedded_chunks": 1}
        )
        client.update_embedding_progress.assert_called_once()
        client.update_status.assert_any_call("run-id", "indexed")


if __name__ == "__main__":
    unittest.main()
