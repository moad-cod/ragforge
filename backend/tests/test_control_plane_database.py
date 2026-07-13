"""PostgreSQL integration coverage for Control Plane Tasks 21 and 22.

Run with:
    RUN_DATABASE_TESTS=1 python -m unittest tests.test_control_plane_database -v
"""

import asyncio
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest
import uuid

from sqlalchemy import func, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
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
from app.repositories.ingestion_runs import update_ingestion_status
from app.repositories.retrieval_logs import get_retrieval_logs_for_query
from app.services.chunk_indexing import qdrant_point_id
from app.services.control_plane_seed import seed_control_plane
from app.services.control_plane_validation import CORE_TABLES, validate_control_plane_schema


BACKEND_DIR = Path(__file__).resolve().parents[1]
RUN_DATABASE_TESTS = os.getenv("RUN_DATABASE_TESTS") == "1"
TEST_ENGINE = None
TEST_SESSION_FACTORY = None
MIGRATION_UP_TABLES = set()
MIGRATION_DOWN_TABLES = set()


def _test_database_url() -> str:
    configured = os.getenv("TEST_DATABASE_URL")
    url = make_url(configured or settings.DATABASE_URL)
    database = url.database if configured else f"{url.database}_test"
    if not database or not database.endswith("_test"):
        raise RuntimeError("Integration tests require a database name ending in '_test'")
    if not re.fullmatch(r"[A-Za-z0-9_]+", database):
        raise RuntimeError("Test database name may contain only letters, digits, and underscores")
    return url.set(database=database).render_as_string(hide_password=False)


async def _ensure_test_database(database_url: str) -> None:
    url = make_url(database_url)
    admin_engine = create_async_engine(
        url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    async with admin_engine.connect() as connection:
        exists = await connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :database"),
            {"database": url.database},
        )
        if not exists:
            await connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    await admin_engine.dispose()


def _run_alembic(database_url: str, *arguments: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
        cwd=BACKEND_DIR,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode:
        raise RuntimeError(
            f"Alembic {' '.join(arguments)} failed:\n{result.stdout}\n{result.stderr}"
        )


async def _table_names(database_url: str) -> set[str]:
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        names = await connection.run_sync(lambda sync_connection: inspect(sync_connection).get_table_names())
    await engine.dispose()
    return set(names)


def setUpModule() -> None:
    if not RUN_DATABASE_TESTS:
        raise unittest.SkipTest("set RUN_DATABASE_TESTS=1 to run PostgreSQL integration tests")

    global TEST_ENGINE, TEST_SESSION_FACTORY, MIGRATION_UP_TABLES, MIGRATION_DOWN_TABLES
    database_url = _test_database_url()
    asyncio.run(_ensure_test_database(database_url))

    _run_alembic(database_url, "upgrade", "head")
    MIGRATION_UP_TABLES = asyncio.run(_table_names(database_url))
    _run_alembic(database_url, "downgrade", "base")
    MIGRATION_DOWN_TABLES = asyncio.run(_table_names(database_url))
    _run_alembic(database_url, "upgrade", "head")

    TEST_ENGINE = create_async_engine(database_url, poolclass=NullPool)
    TEST_SESSION_FACTORY = async_sessionmaker(TEST_ENGINE, expire_on_commit=False)


def tearDownModule() -> None:
    if TEST_ENGINE is None:
        return
    database_url = _test_database_url()
    asyncio.run(TEST_ENGINE.dispose())
    _run_alembic(database_url, "downgrade", "base")


class AlembicRoundTripTests(unittest.TestCase):
    def test_upgrade_creates_and_downgrade_removes_all_core_tables(self):
        self.assertTrue(CORE_TABLES.issubset(MIGRATION_UP_TABLES))
        self.assertTrue(CORE_TABLES.isdisjoint(MIGRATION_DOWN_TABLES))


class ControlPlaneDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = TEST_SESSION_FACTORY()
        try:
            self.seed = await seed_control_plane(db=self.db, namespace=self._testMethodName)
        except Exception:
            await self.db.rollback()
            await self.db.close()
            raise

    async def asyncTearDown(self):
        await self.db.rollback()
        await self.db.close()

    async def test_seed_is_complete_and_idempotent(self):
        repeated = await seed_control_plane(db=self.db, namespace=self._testMethodName)
        self.assertEqual(repeated, self.seed)

        identifiers = {
            Organization: self.seed.organization_id,
            User: self.seed.user_id,
            Project: self.seed.project_id,
            Document: self.seed.document_id,
            DocumentVersion: self.seed.document_version_id,
            IngestionRun: self.seed.ingestion_run_id,
            EmbeddingRun: self.seed.embedding_run_id,
            Chunk: self.seed.chunk_id,
            QueryLog: self.seed.query_log_id,
            RetrievalLog: self.seed.retrieval_log_id,
        }
        for model, identifier in identifiers.items():
            with self.subTest(model=model.__name__):
                count = await self.db.scalar(
                    select(func.count()).select_from(model).where(model.id == identifier)
                )
                self.assertEqual(count, 1)

        query_log = await self.db.get(QueryLog, self.seed.query_log_id)
        self.assertEqual(
            query_log.answer,
            "PostgreSQL stores durable control-plane state.",
        )

    async def test_document_current_version_and_lake_paths_are_linked(self):
        document = await self.db.get(Document, self.seed.document_id)
        version = await self.db.get(DocumentVersion, self.seed.document_version_id)
        self.assertEqual(document.current_version_id, version.id)
        self.assertEqual(version.document_id, document.id)
        self.assertTrue(version.bronze_path.startswith("bronze/"))
        self.assertTrue(version.silver_path.startswith("silver/"))
        self.assertTrue(version.gold_path.startswith("gold/"))

    async def test_ingestion_lifecycle_updates_durable_entities(self):
        run = await self.db.get(IngestionRun, self.seed.ingestion_run_id)
        document = await self.db.get(Document, self.seed.document_id)
        version = await self.db.get(DocumentVersion, self.seed.document_version_id)
        run.status = "landed"
        run.started_at = None
        run.finished_at = None
        document.status = "landed"
        document.current_version_id = None
        version.status = "landed"
        await self.db.flush()

        for status in ("running", "silver_completed", "gold_completed", "indexed"):
            await update_ingestion_status(self.db, run.id, status)

        self.assertEqual(run.status, "indexed")
        self.assertIsNotNone(run.started_at)
        self.assertIsNotNone(run.finished_at)
        self.assertEqual(document.status, "indexed")
        self.assertEqual(document.current_version_id, version.id)
        self.assertEqual(version.status, "indexed")

    async def test_ingestion_failure_records_error(self):
        run = await self.db.get(IngestionRun, self.seed.ingestion_run_id)
        run.status = "running"
        run.finished_at = None
        await self.db.flush()

        await update_ingestion_status(
            self.db,
            run.id,
            "failed",
            error_message="seed validation failure",
        )
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.error_message, "seed validation failure")
        self.assertIsNotNone(run.finished_at)

    async def test_duplicate_qdrant_collection_is_rejected(self):
        project = await self.db.get(Project, self.seed.project_id)
        self.db.add(
            Project(
                id=str(uuid.uuid4()),
                organization_id=self.seed.organization_id,
                name="Duplicate collection",
                qdrant_collection=project.qdrant_collection,
                created_by=self.seed.user_id,
            )
        )
        with self.assertRaises(IntegrityError):
            await self.db.flush()

    async def test_duplicate_chunk_index_is_rejected(self):
        original = await self.db.get(Chunk, self.seed.chunk_id)
        self.db.add(self._duplicate_chunk(original, chunk_index=original.chunk_index))
        with self.assertRaises(IntegrityError):
            await self.db.flush()

    async def test_duplicate_chunk_content_hash_is_rejected(self):
        original = await self.db.get(Chunk, self.seed.chunk_id)
        self.db.add(self._duplicate_chunk(original, content_hash=original.content_hash))
        with self.assertRaises(IntegrityError):
            await self.db.flush()

    async def test_duplicate_qdrant_point_id_is_rejected(self):
        original = await self.db.get(Chunk, self.seed.chunk_id)
        self.db.add(self._duplicate_chunk(original, qdrant_point_id=original.qdrant_point_id))
        with self.assertRaises(IntegrityError):
            await self.db.flush()

    async def test_invalid_foreign_key_is_rejected(self):
        self.db.add(
            QueryLog(
                id=str(uuid.uuid4()),
                project_id=str(uuid.uuid4()),
                user_id=self.seed.user_id,
                question="This project does not exist",
            )
        )
        with self.assertRaises(IntegrityError):
            await self.db.flush()

    async def test_query_and_retrieval_logs_link_to_seeded_chunk(self):
        logs = await get_retrieval_logs_for_query(self.db, self.seed.query_log_id)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].query_log_id, self.seed.query_log_id)
        self.assertEqual(logs[0].chunk_id, self.seed.chunk_id)
        self.assertEqual(logs[0].rank, 1)
        self.assertTrue(logs[0].used_in_answer)

    async def test_qdrant_point_id_is_deterministic(self):
        chunk = await self.db.get(Chunk, self.seed.chunk_id)
        expected = qdrant_point_id(self.seed.document_version_id, chunk.chunk_index)
        self.assertEqual(chunk.qdrant_point_id, expected)
        self.assertEqual(expected, qdrant_point_id(self.seed.document_version_id, 0))

    async def test_final_schema_validation_checklist_passes(self):
        report = await validate_control_plane_schema(TEST_ENGINE)
        self.assertTrue(report.ok, report.missing)

    def _duplicate_chunk(self, original: Chunk, **overrides) -> Chunk:
        values = {
            "id": str(uuid.uuid4()),
            "project_id": original.project_id,
            "document_id": original.document_id,
            "document_version_id": original.document_version_id,
            "ingestion_run_id": original.ingestion_run_id,
            "qdrant_point_id": str(uuid.uuid4()),
            "chunk_index": original.chunk_index + 1,
            "text": f"Duplicate candidate {uuid.uuid4()}",
            "content_hash": str(uuid.uuid4()),
        }
        values.update(overrides)
        return Chunk(**values)


if __name__ == "__main__":
    unittest.main()
