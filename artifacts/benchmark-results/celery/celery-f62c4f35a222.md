# celery-controlled-ingestion

- Experiment ID: `celery-f62c4f35a222`
- Orchestrator: `celery`
- Dataset: `v1`
- Status: `passed`
- Started: `2026-07-30T19:32:13.333879+00:00`
- Finished: `2026-07-30T19:32:19.650497+00:00`
- Concurrency: `1`
- Chunker: `paragraph`

## Summary

- Submitted runs: `3`
- Terminal runs: `3`
- Indexed runs: `3`
- Valid indexed runs: `3`
- Success rate: `1.0`
- Integrity rate: `1.0`
- Throughput runs/min: `28.496`
- Goodput runs/min: `28.496`

## Latency

| Metric | count | p50 ms | p90 ms | p95 ms | p99 ms | max ms |
|---|---:|---:|---:|---:|---:|---:|
| api_acceptance | 3 | 38.587 | 39.425 | 39.425 | 39.425 | 39.425 |
| api_response_after_run_created | 3 | 10.111 | 10.211 | 10.211 | 10.211 | 10.211 |
| end_to_end | 3 | 1301.065 | 1305.374 | 1305.374 | 1305.374 | 1305.374 |
| observed_end_to_end | 3 | 1588.496 | 1809.028 | 1809.028 | 1809.028 | 1809.028 |
| queue_to_start | 3 | 34.301 | 256.048 | 256.048 | 256.048 | 256.048 |
| run_execution | 3 | 1277.714 | 1281.184 | 1281.184 | 1281.184 | 1281.184 |
| submission_to_run_created | 3 | 28.376 | 29.314 | 29.314 | 29.314 | 29.314 |
