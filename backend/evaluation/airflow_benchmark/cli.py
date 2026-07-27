"""Command-line entry point for the Airflow benchmark."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from evaluation.airflow_benchmark.models import BenchmarkConfig
from evaluation.airflow_benchmark.runner import AirflowBenchmarkRunner
from evaluation.airflow_benchmark.workload import load_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a RAGForge Airflow ingestion benchmark.")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--experiment-name", default="airflow-controlled-ingestion")
    parser.add_argument("--dataset-version", default="v1")
    parser.add_argument("--documents", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--chunker", default="paragraph")
    parser.add_argument("--poll-interval-seconds", type=float, default=0.5)
    parser.add_argument("--timeout-seconds", type=float, default=240.0)
    parser.add_argument("--output-dir", type=Path, default=Path("backend/evaluation/results/airflow"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--email")
    parser.add_argument("--password")
    return parser


async def async_main() -> int:
    args = build_parser().parse_args()
    config = BenchmarkConfig(
        api_url=args.api_url,
        experiment_name=args.experiment_name,
        dataset_version=args.dataset_version,
        concurrency=args.concurrency,
        document_count=args.documents,
        chunker=args.chunker,
        poll_interval_seconds=args.poll_interval_seconds,
        timeout_seconds=args.timeout_seconds,
        output_dir=args.output_dir,
        email=args.email,
        password=args.password,
    )
    workload = load_manifest(args.manifest, fallback_chunker=args.chunker) if args.manifest else None
    report = await AirflowBenchmarkRunner(config, workload=workload).run()
    print(f"Experiment {report.experiment_id} finished with status: {report.status}")
    print(f"JSON report: {config.output_dir / f'{report.experiment_id}.json'}")
    print(f"Markdown report: {config.output_dir / f'{report.experiment_id}.md'}")
    return 0 if report.status == "passed" else 1


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
