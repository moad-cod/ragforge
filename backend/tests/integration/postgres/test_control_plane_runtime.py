from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi import BackgroundTasks, HTTPException

from app.api.ingest import get_ingestion_run_status, upload_file
from app.api.internal_pipeline import (
    GoldChunkPayload,
    IndexChunksPayload,
    index_ingestion_run_chunks,
    read_ingestion_run,
    require_pipeline_token,
)
from app.core.config import settings
from app.models import Document, DocumentVersion, IngestionRun
from app.repositories.ingestion_runs import (
    reconcile_stale_dispatch,
    update_ingestion_status,
)
from app.services.bronze_storage import object_key


class ControlPlaneRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_file_upload_lands_in_bronze_and_returns_run(self):
        project = SimpleNamespace(id="project-id", organization_id=None)
        document = SimpleNamespace(id="document-id")
        version = SimpleNamespace(id="version-id")
        run = SimpleNamespace(id="run-id")
        db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
        upload = SimpleNamespace(
            filename="sample.txt",
            content_type="text/plain",
            read=AsyncMock(return_value=b"hello control plane"),
        )

        with (
            patch("app.api.ingest._get_project", AsyncMock(return_value=project)),
            patch("app.api.ingest._get_or_create_document", AsyncMock(return_value=document)),
            patch("app.api.ingest._ensure_new_content", AsyncMock()),
            patch("app.api.ingest._next_version_number", AsyncMock(return_value=1)),
            patch("app.api.ingest.upload_raw_file", Mock(return_value="bronze/key")) as upload_raw,
            patch("app.api.ingest.asyncio.to_thread", AsyncMock(return_value="bronze/key")) as to_thread,
            patch(
                "app.api.ingest.version_repository.create_document_version",
                AsyncMock(return_value=version),
            ) as create_version,
            patch(
                "app.api.ingest.ingestion_repository.create_ingestion_run",
                AsyncMock(return_value=run),
            ) as create_run,
            patch("app.api.ingest.publish_ingestion_event", AsyncMock()) as publish_event,
            patch.object(settings, "AIRFLOW_API_URL", ""),
        ):
            response = await upload_file(
                background_tasks=BackgroundTasks(),
                file=upload,
                project_id="project-id",
                chunker="paragraph",
                db=db,
                user={"user_id": "user-id"},
            )

        self.assertEqual(
            response,
            {
                "document_id": "document-id",
                "document_version_id": "version-id",
                "ingestion_run_id": "run-id",
                "status": "landed",
            },
        )
        to_thread.assert_awaited_once()
        self.assertIs(to_thread.await_args.args[0], upload_raw)
        self.assertEqual(create_version.await_args.kwargs["status"], "landed")
        self.assertIsNone(create_version.await_args.kwargs["silver_path"])
        self.assertEqual(create_run.await_args.kwargs["status"], "landed")
        db.commit.assert_awaited_once()
        publish_event.assert_awaited_once_with(
            "run-id",
            "landed",
            data={"document_id": "document-id", "document_version_id": "version-id"},
        )

    async def test_status_endpoint_reports_durable_pipeline_progress(self):
        run = SimpleNamespace(
            id="run-id",
            document_id="document-id",
            document_version_id="version-id",
            status="gold_completed",
            airflow_dag_run_id="dag-id",
            error_message=None,
        )
        version = SimpleNamespace(bronze_path="bronze/key", silver_path=None, gold_path=None)
        with (
            patch(
                "app.api.ingest.ingestion_repository.get_owned_ingestion_run",
                AsyncMock(return_value=run),
            ),
            patch(
                "app.api.ingest.version_repository.get_document_version",
                AsyncMock(return_value=version),
            ),
        ):
            response = await get_ingestion_run_status(
                "run-id",
                db=SimpleNamespace(),
                user={"user_id": "user-id"},
            )

        self.assertEqual(
            response["progress"],
            {"bronze": True, "silver": True, "gold": True, "qdrant": False},
        )

    async def test_repository_status_update_keeps_entities_consistent(self):
        run = IngestionRun(
            id="00000000-0000-0000-0000-000000000001",
            project_id="00000000-0000-0000-0000-000000000002",
            document_id="00000000-0000-0000-0000-000000000003",
            document_version_id="00000000-0000-0000-0000-000000000004",
            status="running",
            created_by="00000000-0000-0000-0000-000000000005",
        )
        document = Document(
            id=run.document_id,
            project_id=run.project_id,
            status="processing",
            created_by=run.created_by,
        )
        version = DocumentVersion(
            id=run.document_version_id,
            document_id=run.document_id,
            version_number=1,
            content_hash="hash",
            status="processing",
        )
        db = SimpleNamespace(get=AsyncMock(), flush=AsyncMock())

        async def get_model(model, _identifier):
            return {IngestionRun: run, Document: document, DocumentVersion: version}[model]

        db.get.side_effect = get_model
        await update_ingestion_status(
            db,
            run.id,
            "silver_completed",
            silver_path="silver/version/chunks.parquet",
        )
        await update_ingestion_status(
            db,
            run.id,
            "gold_completed",
            gold_path="gold/version/embedded_chunks.parquet",
        )
        result = await update_ingestion_status(db, run.id, "indexed")

        self.assertIs(result, run)
        self.assertEqual(document.status, "indexed")
        self.assertEqual(document.current_version_id, version.id)
        self.assertEqual(version.status, "indexed")
        self.assertEqual(version.silver_path, "silver/version/chunks.parquet")
        self.assertEqual(version.gold_path, "gold/version/embedded_chunks.parquet")
        self.assertIsNotNone(run.finished_at)

    async def test_repository_rejects_artifact_path_before_stage_completes(self):
        run = IngestionRun(
            id="00000000-0000-0000-0000-000000000001",
            project_id="00000000-0000-0000-0000-000000000002",
            document_id="00000000-0000-0000-0000-000000000003",
            document_version_id="00000000-0000-0000-0000-000000000004",
            status="landed",
            created_by="00000000-0000-0000-0000-000000000005",
        )
        db = SimpleNamespace(get=AsyncMock(return_value=run), flush=AsyncMock())

        with self.assertRaisesRegex(ValueError, "silver_path"):
            await update_ingestion_status(
                db,
                run.id,
                "running",
                silver_path="silver/not-created.parquet",
            )
        self.assertEqual(run.status, "landed")

    async def test_repository_rejects_skipped_ingestion_stage(self):
        run = IngestionRun(
            id="00000000-0000-0000-0000-000000000001",
            project_id="00000000-0000-0000-0000-000000000002",
            document_id="00000000-0000-0000-0000-000000000003",
            document_version_id="00000000-0000-0000-0000-000000000004",
            status="landed",
            created_by="00000000-0000-0000-0000-000000000005",
        )
        db = SimpleNamespace(get=AsyncMock(return_value=run), flush=AsyncMock())

        with self.assertRaisesRegex(ValueError, "landed -> indexed"):
            await update_ingestion_status(db, run.id, "indexed")
        db.flush.assert_not_awaited()

    async def test_repository_reconciles_stale_dispatch_to_failed_terminal_state(self):
        run = IngestionRun(
            id="00000000-0000-0000-0000-000000000001",
            project_id="00000000-0000-0000-0000-000000000002",
            document_id="00000000-0000-0000-0000-000000000003",
            document_version_id="00000000-0000-0000-0000-000000000004",
            status="queued",
            created_by="00000000-0000-0000-0000-000000000005",
            created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=10),
        )
        document = Document(
            id=run.document_id,
            project_id=run.project_id,
            status="landed",
            created_by=run.created_by,
        )
        version = DocumentVersion(
            id=run.document_version_id,
            document_id=run.document_id,
            version_number=1,
            content_hash="hash",
            status="landed",
        )
        db = SimpleNamespace(get=AsyncMock(), flush=AsyncMock())

        async def get_model(model, _identifier):
            return {IngestionRun: run, Document: document, DocumentVersion: version}[model]

        db.get.side_effect = get_model
        result = await reconcile_stale_dispatch(
            db,
            run,
            timeout=timedelta(minutes=5),
            error_message="dispatch timed out",
        )

        self.assertIs(result, run)
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.error_message, "dispatch timed out")
        self.assertIsNotNone(run.finished_at)
        self.assertEqual(document.status, "failed")
        self.assertEqual(version.status, "failed")
        db.flush.assert_awaited_once()

    async def test_status_endpoint_reconciles_stale_dispatch_run(self):
        run = SimpleNamespace(
            id="run-id",
            document_id="document-id",
            document_version_id="version-id",
            status="queued",
            airflow_dag_run_id=None,
            error_message=None,
        )
        failed = SimpleNamespace(
            **{
                **run.__dict__,
                "status": "failed",
                "error_message": "dispatch timeout",
                "finished_at": datetime.now(UTC).replace(tzinfo=None),
            }
        )
        version = SimpleNamespace(bronze_path="bronze/key", silver_path=None, gold_path=None)
        db = SimpleNamespace(commit=AsyncMock())

        with (
            patch(
                "app.api.ingest.ingestion_repository.get_owned_ingestion_run",
                AsyncMock(return_value=run),
            ),
            patch(
                "app.api.ingest.ingestion_repository.reconcile_stale_dispatch",
                AsyncMock(return_value=failed),
            ),
            patch(
                "app.api.ingest.version_repository.get_document_version",
                AsyncMock(return_value=version),
            ),
            patch("app.api.ingest.publish_ingestion_event", AsyncMock()) as publish_event,
        ):
            response = await get_ingestion_run_status(
                "run-id",
                db=db,
                user={"user_id": "user-id"},
            )

        self.assertEqual(response["status"], "failed")
        db.commit.assert_awaited_once()
        publish_event.assert_awaited_once()

    def test_pipeline_service_token_is_required(self):
        with patch.object(settings, "PIPELINE_SERVICE_TOKEN", "secret"):
            with self.assertRaises(HTTPException) as context:
                require_pipeline_token("Bearer wrong")
            self.assertEqual(context.exception.status_code, 401)
            self.assertIsNone(require_pipeline_token("Bearer secret"))

    def test_bronze_database_path_maps_to_bucket_object_key(self):
        with patch.object(settings, "MINIO_BUCKET_BRONZE", "bronze"):
            self.assertEqual(object_key("bronze/org_id=x/raw/file.txt"), "org_id=x/raw/file.txt")

    async def test_pipeline_metadata_exposes_artifact_inputs_and_processing_config(self):
        run = SimpleNamespace(
            id="run-id",
            project_id="project-id",
            document_id="document-id",
            document_version_id="version-id",
            status="running",
            airflow_dag_run_id="dag-id",
            error_message=None,
            started_at=None,
            finished_at=None,
            created_at=None,
        )
        project = SimpleNamespace(
            id="project-id",
            organization_id="organization-id",
            qdrant_collection="project_collection",
        )
        document = SimpleNamespace(
            id="document-id",
            filename="sample.txt",
            source_type="file",
            mime_type="text/plain",
        )
        version = SimpleNamespace(
            id="version-id",
            version_number=1,
            bronze_path="bronze/version/raw/sample.txt",
            silver_path=None,
            gold_path=None,
            parser_name="txt",
            chunker_id="paragraph",
            embedding_model="BAAI/bge-small-en-v1.5",
        )
        db = SimpleNamespace(get=AsyncMock())

        async def get_model(model, _identifier):
            from app.models import Document as DocumentModel
            from app.models import DocumentVersion as VersionModel
            from app.models import Project as ProjectModel

            return {
                ProjectModel: project,
                DocumentModel: document,
                VersionModel: version,
            }[model]

        db.get.side_effect = get_model
        with patch(
            "app.api.internal_pipeline.ingestion_repository.get_ingestion_run",
            AsyncMock(return_value=run),
        ):
            response = await read_ingestion_run("run-id", db)

        self.assertEqual(response["bronze_path"], version.bronze_path)
        self.assertEqual(response["chunker_id"], "paragraph")
        self.assertEqual(response["filename"], "sample.txt")
        self.assertEqual(response["qdrant_collection"], "project_collection")
        self.assertEqual(response["ingestion_plan"]["technique_id"], "paragraph")
        self.assertEqual(response["ingestion_plan"]["profile"], "throughput")

    async def test_pipeline_can_index_gold_chunks_for_an_ingestion_run(self):
        run = SimpleNamespace(
            id="run-id",
            project_id="project-id",
            document_id="document-id",
            document_version_id="version-id",
            status="gold_completed",
        )
        project = SimpleNamespace(id="project-id", qdrant_collection="project_collection")
        document = SimpleNamespace(id="document-id")
        version = SimpleNamespace(id="version-id")
        db = SimpleNamespace(get=AsyncMock(), commit=AsyncMock())

        async def get_model(model, _identifier):
            from app.models import Document as DocumentModel
            from app.models import DocumentVersion as VersionModel
            from app.models import Project as ProjectModel

            return {
                ProjectModel: project,
                DocumentModel: document,
                VersionModel: version,
            }[model]

        db.get.side_effect = get_model
        payload = IndexChunksPayload(
            chunks=[
                GoldChunkPayload(
                    chunk_index=0,
                    text="Durable chunk",
                    dense_vector=[0.1, 0.2],
                )
            ]
        )
        with (
            patch(
                "app.api.internal_pipeline.ingestion_repository.get_ingestion_run",
                AsyncMock(return_value=run),
            ),
            patch(
                "app.api.internal_pipeline.index_document_version_chunks",
                AsyncMock(return_value=[SimpleNamespace(id="chunk-id")]),
            ) as index_chunks,
        ):
            response = await index_ingestion_run_chunks("run-id", payload, db)

        self.assertEqual(response["chunks_indexed"], 1)
        self.assertEqual(response["qdrant_collection"], "project_collection")
        self.assertEqual(index_chunks.await_args.kwargs["version"], version)
        self.assertEqual(index_chunks.await_args.kwargs["chunks"][0].chunk_index, 0)
        db.commit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
