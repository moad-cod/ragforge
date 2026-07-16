#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="${E2E_COMPOSE_PROJECT:-ragforge-e2e}"
KEEP_E2E_STACK="${KEEP_E2E_STACK:-0}"

export POSTGRES_PORT="${E2E_POSTGRES_PORT:-15432}"
export QDRANT_PORT="${E2E_QDRANT_PORT:-16333}"
export MINIO_API_PORT="${E2E_MINIO_API_PORT:-19000}"
export MINIO_CONSOLE_PORT="${E2E_MINIO_CONSOLE_PORT:-19001}"
export REDIS_PORT="${E2E_REDIS_PORT:-16379}"
export FASTAPI_PORT="${E2E_FASTAPI_PORT:-18000}"
export AIRFLOW_PORT="${E2E_AIRFLOW_PORT:-18080}"

COMPOSE=(
  docker compose
  --project-name "$PROJECT_NAME"
  --file "$ROOT_DIR/docker-compose.yml"
  --file "$ROOT_DIR/docker-compose.e2e.yml"
  --profile batch
)

SERVICES=(
  postgres
  qdrant
  minio
  redis
  airflow-postgres
  provider-stub
  fastapi
  airflow-apiserver
  airflow-scheduler
  airflow-dag-processor
  airflow-triggerer
)

cleanup() {
  exit_code=$?
  if (( exit_code != 0 )); then
    echo "Task 26 E2E failed; recent service logs follow." >&2
    "${COMPOSE[@]}" logs --no-color --tail=80 \
      fastapi provider-stub airflow-apiserver airflow-scheduler >&2 || true
  fi
  if [[ "$KEEP_E2E_STACK" != "1" ]]; then
    "${COMPOSE[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
  else
    echo "Keeping E2E stack running because KEEP_E2E_STACK=1."
  fi
  exit "$exit_code"
}
trap cleanup EXIT

cd "$ROOT_DIR"

echo "Resetting isolated Compose project: $PROJECT_NAME"
"${COMPOSE[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true

echo "Building FastAPI, Airflow, and deterministic provider images"
"${COMPOSE[@]}" build fastapi airflow-apiserver provider-stub

echo "Starting durable data services"
"${COMPOSE[@]}" up -d --wait postgres qdrant minio redis airflow-postgres

echo "Applying application Alembic migrations"
"${COMPOSE[@]}" run --rm --no-deps fastapi \
  python -m alembic -c alembic.ini upgrade head

echo "Starting API, provider, Airflow, and one-shot initialization services"
"${COMPOSE[@]}" up -d --wait "${SERVICES[@]}"

echo "Running upload-to-answer and cross-system lineage scenario"
"${COMPOSE[@]}" exec -T fastapi \
  python -m unittest \
  tests.e2e.test_control_plane.FullControlPlaneE2ETests.test_upload_to_answer_and_cross_system_lineage \
  -v

echo "Stopping Redis to validate PostgreSQL recovery"
"${COMPOSE[@]}" stop redis
"${COMPOSE[@]}" exec -T fastapi \
  python -m unittest \
  tests.e2e.test_control_plane.FullControlPlaneE2ETests.test_redis_outage_recovers_from_postgres \
  -v

echo "Restarting Redis"
"${COMPOSE[@]}" up -d --wait redis

echo "Running durable failure and tenant-isolation scenarios"
"${COMPOSE[@]}" exec -T fastapi \
  python -m unittest \
  tests.e2e.test_control_plane.FullControlPlaneE2ETests.test_pipeline_failure_is_durable \
  tests.e2e.test_control_plane.FullControlPlaneE2ETests.test_provider_failure_preserves_query_and_retrieval_logs \
  tests.e2e.test_control_plane.FullControlPlaneE2ETests.test_tenant_isolation_for_runs_documents_and_queries \
  -v

echo "Task 26 E2E control-plane validation passed."
