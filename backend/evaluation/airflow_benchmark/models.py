"""Typed records used by the Airflow benchmark runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class BenchmarkConfig:
    api_url: str
    orchestrator: str = "airflow"
    dataset_version: str = "v1"
    experiment_name: str = "airflow-controlled-ingestion"
    concurrency: int = 1
    document_count: int = 3
    chunker: str = "paragraph"
    poll_interval_seconds: float = 0.5
    timeout_seconds: float = 240.0
    output_dir: Path = Path("artifacts/benchmark-results/airflow")
    email: str | None = None
    password: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return json_ready(asdict(self))


@dataclass(frozen=True)
class WorkloadDocument:
    document_id: str
    filename: str
    content: bytes
    mime_type: str
    chunker: str
    profile: str

    @property
    def size_bytes(self) -> int:
        return len(self.content)

    @property
    def document_type(self) -> str:
        suffix = self.filename.rsplit(".", 1)[-1].lower() if "." in self.filename else "unknown"
        return suffix or "unknown"


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    observed: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunMeasurement:
    benchmark_document_id: str
    ingestion_run_id: str | None
    document_id: str | None
    document_version_id: str | None
    filename: str
    chunker: str
    profile: str
    document_size_bytes: int
    document_type: str
    submitted_at: datetime
    upload_accepted_at: datetime | None
    first_seen_status_at: datetime | None
    terminal_observed_at: datetime | None
    status: str
    latency_ms: dict[str, float | None]
    validation: ValidationResult
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return json_ready(asdict(self))


@dataclass(frozen=True)
class ExperimentReport:
    experiment_id: str
    config: BenchmarkConfig
    started_at: datetime
    finished_at: datetime
    status: str
    runs: list[RunMeasurement]
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return json_ready(asdict(self))
