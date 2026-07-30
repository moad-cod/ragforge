"""Airflow benchmark runner for durable RAGForge ingestion."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time
import uuid

from evaluation.airflow_benchmark.client import AirflowBenchmarkClient, BenchmarkIdentity
from evaluation.airflow_benchmark.metrics import summarize_runs
from evaluation.airflow_benchmark.models import (
    BenchmarkConfig,
    ExperimentReport,
    RunMeasurement,
    WorkloadDocument,
    utc_now,
)
from evaluation.airflow_benchmark.report import write_json_report, write_markdown_report
from evaluation.airflow_benchmark.validator import validate_indexed_run
from evaluation.airflow_benchmark.workload import build_default_workload


def parse_api_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def elapsed_ms(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return round((end - start).total_seconds() * 1000.0, 3)


class AirflowBenchmarkRunner:
    def __init__(
        self,
        config: BenchmarkConfig,
        *,
        client: AirflowBenchmarkClient | None = None,
        workload: list[WorkloadDocument] | None = None,
    ) -> None:
        self.config = config
        self.client = client or AirflowBenchmarkClient(config.api_url, timeout_seconds=config.timeout_seconds)
        self.workload = workload or build_default_workload(
            document_count=config.document_count,
            chunker=config.chunker,
            dataset_version=config.dataset_version,
        )

    async def run(self) -> ExperimentReport:
        experiment_id = f"airflow-{uuid.uuid4().hex[:12]}"
        started_at = utc_now()
        monotonic_started = time.monotonic()
        identity = await self.client.create_or_login_identity(
            email=self.config.email,
            password=self.config.password,
        )
        project = await self.client.create_project(
            identity,
            name=f"{self.config.experiment_name}-{experiment_id}",
        )
        semaphore = asyncio.Semaphore(self.config.concurrency)

        async def run_one(workload: WorkloadDocument) -> RunMeasurement:
            async with semaphore:
                return await self._run_one(identity, project["project_id"], workload)

        try:
            runs = await asyncio.gather(*(run_one(item) for item in self.workload))
        finally:
            await self.client.close()

        finished_at = utc_now()
        elapsed_seconds = time.monotonic() - monotonic_started
        summary = summarize_runs(runs, elapsed_seconds=elapsed_seconds)
        status = "passed" if not summary["hard_gate_failures"] else "failed"
        report = ExperimentReport(
            experiment_id=experiment_id,
            config=self.config,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            runs=runs,
            summary=summary,
        )
        write_json_report(report, self.config.output_dir)
        write_markdown_report(report, self.config.output_dir)
        return report

    async def _run_one(
        self,
        identity: BenchmarkIdentity,
        project_id: str,
        workload: WorkloadDocument,
    ) -> RunMeasurement:
        submitted_at = utc_now()
        upload_payload: dict = {}
        run_payload: dict | None = None
        versions: list[dict] = []
        upload_accepted_at: datetime | None = None
        terminal_observed_at: datetime | None = None
        first_seen_status_at: datetime | None = None
        error: str | None = None
        try:
            upload_payload = await self.client.upload_file(
                identity,
                project_id=project_id,
                filename=workload.filename,
                content=workload.content,
                mime_type=workload.mime_type,
                chunker=workload.chunker,
            )
            upload_accepted_at = utc_now()
            run_payload, first_seen_status_at = await self.client.wait_for_terminal_run(
                identity,
                str(upload_payload["ingestion_run_id"]),
                poll_interval_seconds=self.config.poll_interval_seconds,
                timeout_seconds=self.config.timeout_seconds,
            )
            terminal_observed_at = utc_now()
            if upload_payload.get("document_id"):
                versions = await self.client.list_document_versions(
                    identity,
                    str(upload_payload["document_id"]),
                )
        except Exception as exc:
            terminal_observed_at = utc_now()
            error = f"{exc.__class__.__name__}: {exc}"

        validation = validate_indexed_run(
            workload=workload,
            upload_payload=upload_payload,
            run_payload=run_payload,
            versions=versions,
        )
        status = "error" if error else str((run_payload or {}).get("status") or "unknown")
        run_created_at = parse_api_datetime((run_payload or {}).get("created_at"))
        run_started_at = parse_api_datetime((run_payload or {}).get("started_at"))
        run_finished_at = parse_api_datetime((run_payload or {}).get("finished_at"))
        latency_ms = {
            "api_acceptance": elapsed_ms(submitted_at, upload_accepted_at),
            "submission_to_run_created": elapsed_ms(submitted_at, run_created_at),
            "api_response_after_run_created": elapsed_ms(run_created_at, upload_accepted_at),
            "queue_to_start": elapsed_ms(run_created_at, run_started_at),
            "run_execution": elapsed_ms(run_started_at, run_finished_at),
            "end_to_end": elapsed_ms(upload_accepted_at, run_finished_at),
            "observed_end_to_end": elapsed_ms(submitted_at, terminal_observed_at),
        }
        return RunMeasurement(
            benchmark_document_id=workload.document_id,
            ingestion_run_id=upload_payload.get("ingestion_run_id"),
            document_id=upload_payload.get("document_id"),
            document_version_id=upload_payload.get("document_version_id"),
            filename=workload.filename,
            chunker=workload.chunker,
            profile=workload.profile,
            document_size_bytes=workload.size_bytes,
            document_type=workload.document_type,
            submitted_at=submitted_at,
            upload_accepted_at=upload_accepted_at,
            first_seen_status_at=first_seen_status_at,
            terminal_observed_at=terminal_observed_at,
            status=status,
            latency_ms=latency_ms,
            validation=validation,
            error=error,
        )
