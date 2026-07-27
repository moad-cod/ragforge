"""Report writers for benchmark results."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.airflow_benchmark.models import ExperimentReport


def write_json_report(report: ExperimentReport, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{report.experiment_id}.json"
    path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return path


def write_markdown_report(report: ExperimentReport, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = report.summary
    path = output_dir / f"{report.experiment_id}.md"
    lines = [
        f"# {report.config.experiment_name}",
        "",
        f"- Experiment ID: `{report.experiment_id}`",
        f"- Orchestrator: `{report.config.orchestrator}`",
        f"- Dataset: `{report.config.dataset_version}`",
        f"- Status: `{report.status}`",
        f"- Started: `{report.started_at.isoformat()}`",
        f"- Finished: `{report.finished_at.isoformat()}`",
        f"- Concurrency: `{report.config.concurrency}`",
        f"- Chunker: `{report.config.chunker}`",
        "",
        "## Summary",
        "",
        f"- Submitted runs: `{summary['submitted_runs']}`",
        f"- Terminal runs: `{summary['terminal_runs']}`",
        f"- Indexed runs: `{summary['indexed_runs']}`",
        f"- Valid indexed runs: `{summary['validated_indexed_runs']}`",
        f"- Success rate: `{summary['success_rate']}`",
        f"- Integrity rate: `{summary['integrity_rate']}`",
        f"- Throughput runs/min: `{summary['throughput_runs_per_minute']}`",
        f"- Goodput runs/min: `{summary['goodput_runs_per_minute']}`",
        "",
        "## Latency",
        "",
        "| Metric | count | p50 ms | p90 ms | p95 ms | p99 ms | max ms |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for metric, values in summary["latency_ms"].items():
        lines.append(
            "| {metric} | {count} | {p50} | {p90} | {p95} | {p99} | {max_value} |".format(
                metric=metric,
                count=values["count"],
                p50=values["p50"],
                p90=values["p90"],
                p95=values["p95"],
                p99=values["p99"],
                max_value=values["max"],
            )
        )
    failures = summary["hard_gate_failures"]
    if failures:
        lines.extend(["", "## Hard Gate Failures", ""])
        for failure in failures:
            lines.append(
                f"- `{failure['benchmark_document_id']}` / `{failure['ingestion_run_id']}`: "
                + "; ".join(failure["errors"])
            )
    path.write_text("\n".join(lines) + "\n")
    return path
