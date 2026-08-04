from __future__ import annotations

import os
import time
import unittest
from unittest.mock import Mock, patch

from app.services.pipeline_artifacts import (
    bronze_to_silver,
    derive_artifact_path,
    gold_chunks,
    silver_to_gold,
)


class MemoryArtifactStore:
    def __init__(self, objects: dict[str, bytes] | None = None) -> None:
        self.objects = dict(objects or {})
        self.writes: list[str] = []

    def read_bytes(self, path: str) -> bytes:
        return self.objects[path]

    def write_bytes(self, path: str, data: bytes, _content_type: str) -> str:
        self.objects[path] = data
        self.writes.append(path)
        return path


class PipelineArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bronze_path = (
            "bronze/org_id=o/project_id=p/document_id=d/version=1/raw/sample.txt"
        )
        self.store = MemoryArtifactStore(
            {self.bronze_path: b"First source section.\n\nSecond source section."}
        )
        self.run = {
            "bronze_path": self.bronze_path,
            "silver_path": None,
            "gold_path": None,
            "filename": "sample.txt",
            "chunker_id": "paragraph",
        }

    def test_artifact_paths_are_deterministic_siblings_of_bronze(self):
        self.assertEqual(
            derive_artifact_path(self.bronze_path, "silver", "chunks.parquet"),
            "silver/org_id=o/project_id=p/document_id=d/version=1/chunks.parquet",
        )

    def test_pipeline_writes_readable_silver_and_gold_and_can_be_retried(self):
        parser = lambda _data, _filename: ["parsed source"]
        chunker_loader = lambda _chunker_id: (
            lambda _text: ["First durable chunk", "Second durable chunk"]
        )

        silver = bronze_to_silver(
            self.run,
            store=self.store,
            parser=parser,
            chunker_loader=chunker_loader,
        )
        self.assertEqual(silver["chunks"], 2)
        self.run["silver_path"] = silver["artifact_path"]

        gold = silver_to_gold(
            self.run,
            store=self.store,
            embedder=lambda texts: [[float(i), 0.5] for i, _text in enumerate(texts)],
        )
        self.assertEqual(gold["chunks"], 2)
        self.run["gold_path"] = gold["artifact_path"]

        chunks = gold_chunks(self.run, store=self.store)
        self.assertEqual([chunk["chunk_index"] for chunk in chunks], [0, 1])
        self.assertEqual(chunks[0]["dense_vector"], [0.0, 0.5])
        self.assertEqual(chunks[0]["metadata"]["chunker_id"], "paragraph")

        bronze_to_silver(
            self.run,
            store=self.store,
            parser=parser,
            chunker_loader=chunker_loader,
        )
        silver_to_gold(
            self.run,
            store=self.store,
            embedder=lambda texts: [[float(i), 0.5] for i, _text in enumerate(texts)],
        )
        self.assertEqual(len(self.store.objects), 3)
        self.assertEqual(self.store.writes.count(silver["artifact_path"]), 2)
        self.assertEqual(self.store.writes.count(gold["artifact_path"]), 2)

    def test_empty_parse_fails_before_silver_status_can_advance(self):
        with self.assertRaisesRegex(ValueError, "No indexable text"):
            bronze_to_silver(
                self.run,
                store=self.store,
                parser=lambda _data, _filename: [],
                chunker_loader=lambda _chunker_id: lambda _text: [],
            )
        self.assertEqual(self.store.writes, [])

    def test_embedding_count_mismatch_does_not_write_gold(self):
        silver = bronze_to_silver(
            self.run,
            store=self.store,
            parser=lambda _data, _filename: ["source"],
            chunker_loader=lambda _chunker_id: lambda _text: ["indexable chunk"],
        )
        self.run["silver_path"] = silver["artifact_path"]
        with self.assertRaisesRegex(ValueError, "unexpected number"):
            silver_to_gold(self.run, store=self.store, embedder=lambda _texts: [])
        self.assertNotIn(
            "gold/org_id=o/project_id=p/document_id=d/version=1/embedded_chunks.parquet",
            self.store.objects,
        )

    def test_gold_embedding_uses_plan_batch_size(self):
        silver = bronze_to_silver(
            self.run,
            store=self.store,
            parser=lambda _data, _filename: ["source"],
            chunker_loader=lambda _chunker_id: (
                lambda _text: [f"chunk {index}" for index in range(5)]
            ),
        )
        self.run["silver_path"] = silver["artifact_path"]
        self.run["ingestion_plan"] = {"embedding_batch_size": 2}
        batch_sizes = []

        def embed(texts):
            batch_sizes.append(len(texts))
            return [[float(len(text)), 0.5] for text in texts]

        gold = silver_to_gold(self.run, store=self.store, embedder=embed)

        self.assertEqual(gold["chunks"], 5)
        self.assertEqual(batch_sizes, [2, 2, 1])

    def test_gold_embedding_reports_actual_batch_progress(self):
        silver = bronze_to_silver(
            self.run,
            store=self.store,
            parser=lambda _data, _filename: ["source"],
            chunker_loader=lambda _chunker_id: (
                lambda _text: [f"chunk {index}" for index in range(5)]
            ),
        )
        self.run["silver_path"] = silver["artifact_path"]
        self.run["ingestion_plan"] = {"embedding_batch_size": 2}
        events = []

        gold = silver_to_gold(
            self.run,
            store=self.store,
            embedder=lambda texts: [[float(len(text)), 0.5] for text in texts],
            progress_callback=events.append,
        )

        self.assertEqual(gold["chunks"], 5)
        self.assertEqual([event["stage"] for event in events], ["running", "running", "running", "running", "completed"])
        self.assertEqual([event["embedded_chunks"] for event in events], [0, 2, 4, 5, 5])
        self.assertEqual(events[-1]["total_batches"], 3)

    def test_invalid_plan_batch_size_fails_cleanly(self):
        silver = bronze_to_silver(
            self.run,
            store=self.store,
            parser=lambda _data, _filename: ["source"],
            chunker_loader=lambda _chunker_id: lambda _text: ["indexable chunk"],
        )
        self.run["silver_path"] = silver["artifact_path"]
        self.run["ingestion_plan"] = {"embedding_batch_size": 0}

        with self.assertRaisesRegex(ValueError, "must be positive"):
            silver_to_gold(self.run, store=self.store, embedder=lambda _texts: [])

    def test_embedding_timeout_fails_without_writing_gold(self):
        silver = bronze_to_silver(
            self.run,
            store=self.store,
            parser=lambda _data, _filename: ["source"],
            chunker_loader=lambda _chunker_id: lambda _text: ["slow chunk"],
        )
        self.run["silver_path"] = silver["artifact_path"]

        def slow_embed(texts):
            time.sleep(0.01)
            return [[1.0, 0.5] for _text in texts]

        with patch.dict(os.environ, {"EMBEDDING_TIMEOUT_SECONDS": "0.001"}):
            with self.assertRaisesRegex(TimeoutError, "Embedding stage timed out"):
                silver_to_gold(self.run, store=self.store, embedder=slow_embed)

        self.assertNotIn(
            "gold/org_id=o/project_id=p/document_id=d/version=1/embedded_chunks.parquet",
            self.store.objects,
        )

    def test_embedding_dimension_mismatch_fails_before_qdrant(self):
        silver = bronze_to_silver(
            self.run,
            store=self.store,
            parser=lambda _data, _filename: ["source"],
            chunker_loader=lambda _chunker_id: lambda _text: ["indexable chunk"],
        )
        self.run["silver_path"] = silver["artifact_path"]
        self.run["embedding_dimension"] = 3

        with self.assertRaisesRegex(ValueError, "dimension mismatch before Qdrant"):
            silver_to_gold(
                self.run,
                store=self.store,
                embedder=lambda _texts: [[1.0, 0.5]],
            )

        self.assertNotIn(
            "gold/org_id=o/project_id=p/document_id=d/version=1/embedded_chunks.parquet",
            self.store.objects,
        )

    def test_late_chunking_reuses_contextual_embeddings_in_gold(self):
        self.run["chunker_id"] = "late_chunking"
        with patch(
            "app.services.chunkers.late_chunking.chunk_with_embeddings",
            return_value=(["contextual chunk"], [[0.25, 0.75]]),
        ):
            silver = bronze_to_silver(
                self.run,
                store=self.store,
                parser=lambda _data, _filename: ["source"],
            )
        self.run["silver_path"] = silver["artifact_path"]
        embedder = Mock(side_effect=AssertionError("late vectors must not be recomputed"))

        gold = silver_to_gold(self.run, store=self.store, embedder=embedder)
        self.run["gold_path"] = gold["artifact_path"]
        chunks = gold_chunks(self.run, store=self.store)

        embedder.assert_not_called()
        self.assertTrue(gold["reused_precomputed_embeddings"])
        self.assertEqual(gold["embedding_batches"], 0)
        self.assertEqual(chunks[0]["dense_vector"], [0.25, 0.75])

    def test_unknown_embedding_model_fails_instead_of_mislabeling_gold(self):
        silver = bronze_to_silver(
            self.run,
            store=self.store,
            parser=lambda _data, _filename: ["source"],
            chunker_loader=lambda _chunker_id: lambda _text: ["indexable chunk"],
        )
        self.run["silver_path"] = silver["artifact_path"]
        self.run["embedding_model"] = "unsupported/model"
        with self.assertRaisesRegex(ValueError, "Unsupported pipeline embedding model"):
            silver_to_gold(self.run, store=self.store)


if __name__ == "__main__":
    unittest.main()
