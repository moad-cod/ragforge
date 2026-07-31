"""Shared ingestion benchmark metrics for orchestrator comparisons."""

from __future__ import annotations

from math import ceil
from statistics import mean, median, pstdev
from typing import Any, Protocol


class ValidationLike(Protocol):
    valid: bool
    errors: list[str]


class RunMeasurementLike(Protocol):
    benchmark_document_id: str
    ingestion_run_id: str
    status: str
    latency_ms: dict[str, float | None]
    validation: ValidationLike


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    rank = ceil((percentile_value / 100.0) * len(ordered)) - 1
    index = min(max(rank, 0), len(ordered) - 1)
    return round(ordered[index], 3)


def distribution(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "stddev": None,
            "p50": None,
            "p90": None,
            "p95": None,
            "p99": None,
        }
    return {
        "count": len(values),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
        "mean": round(mean(values), 3),
        "median": round(median(values), 3),
        "stddev": round(pstdev(values), 3) if len(values) > 1 else 0.0,
        "p50": percentile(values, 50),
        "p90": percentile(values, 90),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
    }


def summarize_runs(runs: list[RunMeasurementLike], *, elapsed_seconds: float) -> dict[str, Any]:
    terminal = [run for run in runs if run.status in {"indexed", "failed", "cancelled", "error"}]
    valid = [run for run in runs if run.validation.valid and run.status == "indexed"]
    indexed = [run for run in runs if run.status == "indexed"]
    failures = [run for run in runs if run.status in {"failed", "cancelled", "error"} or not run.validation.valid]
    latency_keys = sorted({key for run in runs for key in run.latency_ms})
    latency = {
        key: distribution(
            [
                value
                for run in runs
                for value in [run.latency_ms.get(key)]
                if isinstance(value, (int, float))
            ]
        )
        for key in latency_keys
    }
    elapsed_minutes = elapsed_seconds / 60.0 if elapsed_seconds > 0 else 0.0
    return {
        "submitted_runs": len(runs),
        "terminal_runs": len(terminal),
        "indexed_runs": len(indexed),
        "validated_indexed_runs": len(valid),
        "failed_or_invalid_runs": len(failures),
        "success_rate": round(len(indexed) / len(runs), 4) if runs else 0.0,
        "integrity_rate": round(len(valid) / len(indexed), 4) if indexed else 0.0,
        "throughput_runs_per_minute": round(len(terminal) / elapsed_minutes, 3) if elapsed_minutes else 0.0,
        "goodput_runs_per_minute": round(len(valid) / elapsed_minutes, 3) if elapsed_minutes else 0.0,
        "latency_ms": latency,
        "hard_gate_failures": [
            {
                "benchmark_document_id": run.benchmark_document_id,
                "ingestion_run_id": run.ingestion_run_id,
                "errors": run.validation.errors,
            }
            for run in runs
            if run.validation.errors
        ],
    }
