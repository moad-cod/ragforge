import hashlib
from pathlib import Path
import tempfile
import unittest

from evaluation.airflow_benchmark.metrics import distribution, percentile, summarize_runs
from evaluation.airflow_benchmark.models import RunMeasurement, ValidationResult, WorkloadDocument, utc_now
from evaluation.airflow_benchmark.validator import validate_indexed_run
from evaluation.airflow_benchmark.workload import build_default_workload, load_manifest


class AirflowBenchmarkMetricsTests(unittest.TestCase):
    def test_percentiles_use_nearest_rank(self):
        values = [100.0, 200.0, 300.0, 400.0]

        self.assertEqual(percentile(values, 50), 200.0)
        self.assertEqual(percentile(values, 95), 400.0)

    def test_distribution_handles_empty_values(self):
        result = distribution([])

        self.assertEqual(result["count"], 0)
        self.assertIsNone(result["p95"])

    def test_summary_calculates_goodput_and_integrity(self):
        now = utc_now()
        runs = [
            RunMeasurement(
                benchmark_document_id="doc-1",
                ingestion_run_id="run-1",
                document_id="document-1",
                document_version_id="version-1",
                filename="doc-1.txt",
                chunker="paragraph",
                profile="throughput",
                document_size_bytes=12,
                document_type="txt",
                submitted_at=now,
                upload_accepted_at=now,
                first_seen_status_at=now,
                terminal_observed_at=now,
                status="indexed",
                latency_ms={"end_to_end": 1000.0},
                validation=ValidationResult(valid=True),
            ),
            RunMeasurement(
                benchmark_document_id="doc-2",
                ingestion_run_id="run-2",
                document_id="document-2",
                document_version_id="version-2",
                filename="doc-2.txt",
                chunker="paragraph",
                profile="throughput",
                document_size_bytes=12,
                document_type="txt",
                submitted_at=now,
                upload_accepted_at=now,
                first_seen_status_at=now,
                terminal_observed_at=now,
                status="failed",
                latency_ms={"end_to_end": 2000.0},
                validation=ValidationResult(valid=False, errors=["failed"]),
            ),
        ]

        summary = summarize_runs(runs, elapsed_seconds=60.0)

        self.assertEqual(summary["submitted_runs"], 2)
        self.assertEqual(summary["validated_indexed_runs"], 1)
        self.assertEqual(summary["goodput_runs_per_minute"], 1.0)
        self.assertEqual(summary["integrity_rate"], 1.0)
        self.assertEqual(summary["latency_ms"]["end_to_end"]["p95"], 2000.0)


class AirflowBenchmarkWorkloadTests(unittest.TestCase):
    def test_default_workload_is_deterministic_and_profiled(self):
        workload = build_default_workload(document_count=2, chunker="semantic", dataset_version="v1")

        self.assertEqual(len(workload), 2)
        self.assertEqual(workload[0].profile, "embedding_aware")
        self.assertTrue(workload[0].content.startswith(b"v1_airflow_doc_0001"))

    def test_manifest_loader_validates_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = b"benchmark payload"
            digest = hashlib.sha256(data).hexdigest()
            (root / "sample.txt").write_bytes(data)
            manifest = root / "documents.json"
            manifest.write_text(
                '{"documents":[{"document_id":"sample","filename":"sample.txt",'
                '"path":"sample.txt","mime_type":"text/plain","sha256":"'
                + digest
                + '"}]}'
            )

            workload = load_manifest(manifest, fallback_chunker="paragraph")

        self.assertEqual(workload[0].filename, "sample.txt")
        self.assertEqual(workload[0].content, data)


class AirflowBenchmarkValidatorTests(unittest.TestCase):
    def setUp(self):
        self.workload = WorkloadDocument(
            document_id="benchmark-doc",
            filename="benchmark.txt",
            content=b"hello",
            mime_type="text/plain",
            chunker="paragraph",
            profile="throughput",
        )
        self.upload = {
            "status": "landed",
            "ingestion_run_id": "run-id",
            "document_id": "document-id",
            "document_version_id": "version-id",
        }

    def test_valid_indexed_run_passes_api_visible_hard_gates(self):
        run = {
            "status": "indexed",
            "document_id": "document-id",
            "document_version_id": "version-id",
            "progress": {"bronze": True, "silver": True, "gold": True, "qdrant": True},
        }
        versions = [
            {
                "document_version_id": "version-id",
                "status": "indexed",
                "bronze_path": "bronze/path",
                "silver_path": "silver/path",
                "gold_path": "gold/path",
                "chunker_id": "paragraph",
            }
        ]

        result = validate_indexed_run(
            workload=self.workload,
            upload_payload=self.upload,
            run_payload=run,
            versions=versions,
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.errors, [])

    def test_missing_artifacts_fail_validation(self):
        run = {
            "status": "indexed",
            "document_id": "document-id",
            "document_version_id": "version-id",
            "progress": {"bronze": True, "silver": False, "gold": True, "qdrant": True},
        }
        versions = [
            {
                "document_version_id": "version-id",
                "status": "indexed",
                "bronze_path": "bronze/path",
                "silver_path": None,
                "gold_path": "gold/path",
                "chunker_id": "paragraph",
            }
        ]

        result = validate_indexed_run(
            workload=self.workload,
            upload_payload=self.upload,
            run_payload=run,
            versions=versions,
        )

        self.assertFalse(result.valid)
        self.assertTrue(any("silver" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
