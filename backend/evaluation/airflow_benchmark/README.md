# Airflow Benchmark

This package implements the Airflow side of the RAGForge orchestrator evaluation framework.

It drives the current FastAPI file-ingestion endpoint, waits for the Airflow-backed ingestion
run to reach a terminal state, validates the API-visible hard gates, and writes JSON plus
Markdown reports.

Run from the repository root:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m evaluation.airflow_benchmark.cli \
  --api-url http://localhost:8000 \
  --documents 10 \
  --concurrency 2 \
  --chunker paragraph
```

Reports are written to:

```text
artifacts/benchmark-results/airflow/
```

The runner can also use a dataset manifest:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m evaluation.airflow_benchmark.cli \
  --manifest backend/evaluation/datasets/v1/manifests/documents.json
```
