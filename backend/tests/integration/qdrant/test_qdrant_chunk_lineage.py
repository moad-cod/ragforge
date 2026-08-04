from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import AsyncMock, Mock, patch

from qdrant_client.models import SparseVector

from app.services.chunk_indexing import (
    GoldChunk,
    chunk_lineage_id,
    index_document_version_chunks,
    postgres_chunk_id,
    qdrant_point_id,
    rebuild_document_version_index,
)


class QdrantChunkLineageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.project = SimpleNamespace(
            id="10000000-0000-0000-0000-000000000001",
            organization_id="10000000-0000-0000-0000-000000000002",
            qdrant_collection="project_10000000_0000_0000_0000_000000000001",
        )
        self.document = SimpleNamespace(
            id="20000000-0000-0000-0000-000000000001",
            project_id=self.project.id,
            filename="architecture.pdf",
            source_type="file",
        )
        self.version = SimpleNamespace(
            id="30000000-0000-0000-0000-000000000001",
            document_id=self.document.id,
        )
        self.run = SimpleNamespace(
            id="40000000-0000-0000-0000-000000000001",
            document_version_id=self.version.id,
        )
        self.chunks = [
            GoldChunk(
                chunk_index=0,
                text="RAGForge stores vectors in Qdrant.",
                dense_vector=[0.1, 0.2, 0.3],
                token_count=7,
                page_start=4,
                page_end=4,
                section_title="Architecture",
                metadata={"language": "en"},
            ),
            GoldChunk(
                chunk_index=1,
                text="PostgreSQL stores durable chunk lineage.",
                dense_vector=[0.4, 0.5, 0.6],
                token_count=6,
                page_start=5,
                page_end=5,
            ),
        ]

    def test_point_ids_are_stable_valid_uuids_derived_from_lineage(self):
        readable = chunk_lineage_id(self.version.id, 12)
        first = qdrant_point_id(self.version.id, 12)

        self.assertEqual(readable, f"{self.version.id}:12")
        self.assertEqual(first, qdrant_point_id(self.version.id, 12))
        self.assertNotEqual(first, qdrant_point_id(self.version.id, 13))
        self.assertEqual(str(uuid.UUID(first)), first)
        self.assertEqual(
            postgres_chunk_id(self.version.id, 12),
            postgres_chunk_id(self.version.id, 12),
        )

    async def test_indexing_persists_complete_lineage_and_qdrant_payload(self):
        client = Mock()
        client.get_collections.return_value = SimpleNamespace(collections=[])
        stored_rows = [SimpleNamespace(id="stored-0"), SimpleNamespace(id="stored-1")]

        with patch(
            "app.services.chunk_indexing.replace_chunks_for_document_version",
            AsyncMock(return_value=stored_rows),
        ) as replace_chunks:
            result = await index_document_version_chunks(
                SimpleNamespace(),
                project=self.project,
                document=self.document,
                version=self.version,
                ingestion_run=self.run,
                chunks=self.chunks,
                client=client,
                sparse_embedder=lambda texts: [
                    SparseVector(indices=[index], values=[1.0])
                    for index, _text in enumerate(texts)
                ],
            )

        self.assertIs(result, stored_rows)
        client.create_collection.assert_called_once()
        client.delete.assert_called_once()
        client.upsert.assert_called_once()

        delete_filter = client.delete.call_args.kwargs["points_selector"]
        self.assertEqual(delete_filter.must[0].key, "document_version_id")
        self.assertEqual(delete_filter.must[0].match.value, self.version.id)

        points = client.upsert.call_args.kwargs["points"]
        self.assertEqual(len(points), 2)
        first_payload = points[0].payload
        self.assertEqual(points[0].id, qdrant_point_id(self.version.id, 0))
        self.assertEqual(first_payload["organization_id"], self.project.organization_id)
        self.assertEqual(first_payload["project_id"], self.project.id)
        self.assertEqual(first_payload["document_id"], self.document.id)
        self.assertEqual(first_payload["document_version_id"], self.version.id)
        self.assertEqual(first_payload["lineage_id"], f"{self.version.id}:0")
        self.assertEqual(first_payload["chunk_id"], postgres_chunk_id(self.version.id, 0))
        self.assertEqual(first_payload["title"], self.document.filename)
        self.assertEqual(first_payload["source_type"], self.document.source_type)
        self.assertEqual(first_payload["section_title"], "Architecture")
        self.assertEqual(first_payload["text"], self.chunks[0].text)

        rows = replace_chunks.await_args.args[2]
        self.assertEqual(replace_chunks.await_args.args[1], self.version.id)
        self.assertEqual(rows[0]["qdrant_point_id"], points[0].id)
        self.assertEqual(rows[0]["document_version_id"], self.version.id)
        self.assertEqual(rows[0]["ingestion_run_id"], self.run.id)
        self.assertEqual(rows[0]["metadata_json"], {"language": "en"})

    async def test_rebuild_uses_the_same_deterministic_indexing_path(self):
        client = Mock()
        client.get_collections.return_value = SimpleNamespace(collections=[])
        with patch(
            "app.services.chunk_indexing.replace_chunks_for_document_version",
            AsyncMock(return_value=[]),
        ):
            await rebuild_document_version_index(
                SimpleNamespace(),
                project=self.project,
                document=self.document,
                version=self.version,
                ingestion_run=self.run,
                chunks=self.chunks[:1],
                client=client,
                sparse_embedder=lambda _texts: [SparseVector(indices=[1], values=[1.0])],
            )

        point = client.upsert.call_args.kwargs["points"][0]
        self.assertEqual(point.id, qdrant_point_id(self.version.id, 0))

    async def test_indexing_rejects_cross_project_lineage(self):
        wrong_document = SimpleNamespace(
            id=self.document.id,
            project_id="different-project",
            filename=self.document.filename,
            source_type=self.document.source_type,
        )
        with self.assertRaisesRegex(ValueError, "does not belong"):
            await index_document_version_chunks(
                SimpleNamespace(),
                project=self.project,
                document=wrong_document,
                version=self.version,
                ingestion_run=self.run,
                chunks=self.chunks,
                sparse_embedder=lambda _texts: [],
            )

    async def test_duplicate_chunk_indexes_are_rejected_before_qdrant_write(self):
        duplicate = [self.chunks[0], self.chunks[0]]
        client = Mock()
        with self.assertRaisesRegex(ValueError, "Duplicate chunk_index"):
            await index_document_version_chunks(
                SimpleNamespace(),
                project=self.project,
                document=self.document,
                version=self.version,
                ingestion_run=self.run,
                chunks=duplicate,
                client=client,
            )
        client.upsert.assert_not_called()

    async def test_duplicate_content_hashes_are_indexed_with_distinct_lineage(self):
        chunks = [
            GoldChunk(chunk_index=0, text="Repeated footer", dense_vector=[0.1, 0.2]),
            GoldChunk(chunk_index=1, text="Repeated footer", dense_vector=[0.3, 0.4]),
        ]
        client = Mock()
        client.get_collections.return_value = SimpleNamespace(collections=[])
        stored_rows = [SimpleNamespace(id="stored-0"), SimpleNamespace(id="stored-1")]

        with patch(
            "app.services.chunk_indexing.replace_chunks_for_document_version",
            AsyncMock(return_value=stored_rows),
        ) as replace_chunks:
            result = await index_document_version_chunks(
                SimpleNamespace(),
                project=self.project,
                document=self.document,
                version=self.version,
                ingestion_run=self.run,
                chunks=chunks,
                client=client,
                sparse_embedder=lambda texts: [
                    SparseVector(indices=[index], values=[1.0])
                    for index, _text in enumerate(texts)
                ],
            )

        self.assertIs(result, stored_rows)
        points = client.upsert.call_args.kwargs["points"]
        self.assertEqual(points[0].id, qdrant_point_id(self.version.id, 0))
        self.assertEqual(points[1].id, qdrant_point_id(self.version.id, 1))
        rows = replace_chunks.await_args.args[2]
        self.assertEqual(rows[0]["content_hash"], rows[1]["content_hash"])
        self.assertNotEqual(rows[0]["qdrant_point_id"], rows[1]["qdrant_point_id"])


if __name__ == "__main__":
    unittest.main()
