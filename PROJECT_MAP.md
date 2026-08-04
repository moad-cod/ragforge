# RAGForge Project Map

RAGForge is a FastAPI SaaS backend for authenticated Retrieval-Augmented Generation. It ingests files and web sources, versions document content, chunks and embeds text, stores dense and sparse vectors in Qdrant, and answers questions through OpenAI-compatible LLM providers. PostgreSQL defines the durable control plane for identities, projects, ingestion runs, chunk lineage, embedding runs, query history, and retrieval traces.

The most complete path is asynchronous file ingestion through MinIO and a selectable orchestrator: Airflow or Celery. URL, Google Drive, and multimodal ingestion are still synchronous paths and do not create the same run/artifact/chunk lineage. The default backend is optimized for text RAG; ColQwen2 multimodal ingestion and CrossEncoder reranking are kept out of the default requirements.

## Architecture

```text
Next.js control-plane UI / Swagger UI
  -> HttpOnly session cookie + same-origin authenticated proxy
  -> FastAPI routers
  -> Auth / Organizations / Projects / Documents / Chunkers / Ingest / Query
  -> SQLAlchemy async + PostgreSQL control-plane metadata
  -> Durable file landing + adaptive ingestion planner
  -> Orchestrator boundary selects Airflow DAG or Celery chain
  -> Bronze -> Silver -> Gold -> Qdrant durable ingestion stages
  -> Parser + chunker registry + embedding services
  -> FastEmbed dense BGE vectors + FastEmbed BM25 sparse vectors
  -> Qdrant dense+sparse vector collections
  -> Hybrid retrieval + optional reranking
  -> Gemini or Groq chat completion
```

## Main Runtime Modules

| Area | Files | Responsibility |
|---|---|---|
| Frontend app | `frontend/src/app/*` | Authenticated App Router pages, layouts, proxy routes, and responsive workspace |
| Frontend features | `frontend/src/components/*`, `frontend/src/hooks/*` | Projects, documents, ingestion SSE recovery, streaming chat, query history, retrieval traces |
| Frontend data | `frontend/src/lib/*` | Typed API client, SSE parser, shared control-plane types, session helpers |
| App entry | `backend/app/main.py` | Creates the FastAPI app and mounts routers |
| Config | `backend/app/core/config.py` | Loads `.env`, required URLs/secrets, optional LLM/R2 settings, limits |
| Auth | `backend/app/core/auth.py`, `backend/app/api/auth.py` | JWT dependency, register, login, current-user read/update/delete |
| Database | `backend/app/core/db.py` | Async SQLAlchemy engine, session dependency, declarative `Base` |
| Models | `backend/app/models/*.py` | One SQLAlchemy model per control-plane table, relationships, constraints, and indexes; `tables.py` remains a compatibility export |
| Organizations | `backend/app/api/organizations.py` | Organization CRUD and soft delete |
| Projects | `backend/app/api/projects.py` | Project CRUD, ownership checks, Qdrant collection lifecycle |
| Documents | `backend/app/api/documents.py` | Document list/get/delete and document version listing |
| Ingestion | `backend/app/api/ingest.py` | File, URL, Google Drive, and optional multimodal ingestion |
| Pipeline control | `backend/app/api/internal_pipeline.py`, `backend/app/services/ingestion_orchestrator.py`, `backend/app/services/ingestion_planner.py` | Authenticated run metadata/status/progress boundary, Airflow/Celery selection, and deterministic technique-to-execution planning |
| Batch artifacts | `backend/app/services/pipeline_artifacts.py`, `backend/jobs/*.py` | Bronze parsing/chunking, shared stage functions, Silver/Gold Parquet, bounded embedding batches/progress callbacks, and Qdrant indexing |
| Airflow execution | `backend/airflow/dags/ragforge_ingestion.py`, `backend/jobs/ingestion_execution.py` | Detects the selected chunking technique, chooses profile-aware commands, exports resource hints, and applies embedding-stage subprocess timeouts |
| Celery execution | `backend/app/workers/celery_app.py`, `backend/app/workers/tasks.py`, `backend/worker.py` | Configures the Celery app, publishes the ingestion chain, retries failed stages, and exposes the worker entry point |
| Benchmarks | `backend/evaluation/airflow_benchmark/*`, `backend/evaluation/celery_benchmark/*` | Matched orchestration benchmark CLIs, clients, workloads, validators, metrics, and report writers |
| Query | `backend/app/api/query.py` | Text and multimodal queries, query SSE, history, and retrieval trace responses |
| Chunker catalog | `backend/app/api/chunkers.py`, `backend/app/services/chunkers/registry.py` | Public chunker metadata, validation, and lazy callable lookup |
| Parsing | `backend/app/services/parser.py` | PDF, DOCX, XLSX, PPTX, CSV, HTML, text, URL, and Google Drive parsing |
| Dense embeddings | `backend/app/services/embedder.py` | Configurable FastEmbed or deterministic embeddings with per-worker model caching and readiness metadata |
| Indexing | `backend/app/services/indexer.py`, `backend/app/services/chunk_indexing.py` | Legacy/direct Qdrant writes plus deterministic PostgreSQL-Qdrant lineage for durable file ingestion |
| Retrieval | `backend/app/services/retriever.py`, `backend/app/services/retrieval/*` | Dense/sparse hybrid search, BM25 sparse embeddings, optional reranking |
| Realtime and cache | `backend/app/services/event_stream.py`, `backend/app/services/query_cache.py` | Redis-backed ingestion replay/fan-out and best-effort query response caching |
| Storage | `backend/app/services/bronze_storage.py`, `backend/app/services/pipeline_artifacts.py`, `backend/app/services/storage.py` | MinIO Bronze/Silver/Gold objects with bounded S3 timeouts and Bronze bucket validation; Cloudflare R2 multimodal page images |

## Repository Structure

```text
backend/
  BACKEND_MAP.md
  Dockerfile
  .dockerignore
  requirements.txt
  app/
    api/
      auth.py
      chunkers.py
      documents.py
      ingest.py
      internal_pipeline.py
      organizations.py
      projects.py
      query.py
    core/
      auth.py
      config.py
      db.py
    repositories/
      projects.py
      documents.py
      document_versions.py
      ingestion_runs.py
      chunks.py
      embedding_runs.py
      query_logs.py
      retrieval_logs.py
    models/
      __init__.py
      organization.py
      user.py
      project.py
      document.py
      document_version.py
      ingestion_run.py
      chunk.py
      embedding_run.py
      query_log.py
      retrieval_log.py
      statuses.py
      tables.py
    services/
      chunkers/
      retrieval/
      embedder.py
      indexer.py
      parser.py
      retriever.py
      storage.py
      bronze_storage.py
      airflow.py
      ingestion_orchestrator.py
      event_stream.py
      chunk_indexing.py
      query_cache.py
      query_observability.py
      pipeline_status.py
      pipeline_artifacts.py
      ingestion_planner.py
      control_plane_seed.py
      control_plane_validation.py
    workers/
      celery_app.py
      tasks.py
  jobs/
    bronze_to_silver.py
    control_plane.py
    ingestion_execution.py
    ingestion_workflow.py
    silver_to_gold.py
    upsert_qdrant.py
  alembic/
    env.py
    versions/
      20260711_0001_create_ragforge_v2_database_schema.py
      20260713_0002_add_query_answer.py
  airflow/
    Dockerfile
    pipeline-requirements.txt
    dags/ragforge_ingestion.py
    plugins/ragforge_control_plane.py
  evaluation/
    configs/
    metrics/
    airflow_benchmark/
    celery_benchmark/
    legacy/
  scripts/
    check_data.py
    cleanup.py
    create_tables.py
    reset_dev_db.py
    seed_control_plane.py
    validate_control_plane.py
  worker.py
  alembic.ini
  tests/
    unit/
    integration/
    e2e/
    benchmarks/
    fixtures/
frontend/
  Dockerfile
  src/
    app/
    components/
    hooks/
    lib/
    test/
docs/
  architecture/
    control-plane.md
    data-model.png
    document-lifecycle.png
    system-design.png
  research/
    evaluation-framework.md
  reports/
    optimization-review.md
  plans/
    ragforge-v2-build-plan.md
artifacts/
  benchmark-results/
  test-results/
scripts/
  e2e_v2.sh
  init_minio.sh
Makefile
docker-compose.yml
test_chunkers.sh
PROJECT_MAP.md
README.md
```

## Data Model

```text
Organization
  id, name, created_at, updated_at, deleted_at
  has many Users
  has many Projects

User
  id, organization_id, email, full_name, hashed_password
  created_at, updated_at, deleted_at
  belongs to Organization
  creates many Projects

Project
  id, organization_id, name, qdrant_collection, created_by
  created_at, updated_at, deleted_at
  belongs to Organization
  belongs to creator User
  has many Documents

Document
  id, project_id, current_version_id, source_type, filename
  mime_type, extension, status, created_by
  created_at, updated_at, deleted_at
  belongs to Project
  has many DocumentVersions

DocumentVersion
  id, document_id, version_number, content_hash
  bronze_path, silver_path, gold_path
  parser_name, chunker_id, embedding_model
  status, error_message, created_at
  belongs to Document

IngestionRun
  id, project_id, document_id, document_version_id, status
  started_at, finished_at, error_message, airflow_dag_run_id
  airflow_dag_run_id is currently a legacy orchestration-id field used by both Airflow and Celery
  created_by, created_at
  belongs to Project, Document, DocumentVersion, and creator User

Chunk
  id, project_id, document_id, document_version_id, ingestion_run_id
  qdrant_point_id, chunk_index, text, content_hash, token/page metadata
  metadata_json, created_at
  belongs to Project, Document, DocumentVersion, and optional IngestionRun

EmbeddingRun
  id, project_id, document_version_id, embedding_model, status
  total_chunks, embedded_chunks, total_batches, embedded_batches
  batch size, backend/device/dimension, attempt, heartbeat, timestamps, error
  belongs to Project and DocumentVersion

QueryLog
  id, project_id, user_id, question, answer, normalized_question_hash
  provider, model, latency_ms, cache_hit, route, evaluation scores
  belongs to Project and User

RetrievalLog
  id, query_log_id, chunk_id, qdrant_score, rerank_score
  rank, retrieval_strategy, used_in_answer, created_at
  belongs to QueryLog and optionally Chunk
```

Projects use UUID-based Qdrant collection names (`project_<uuid>`) so display names can be changed without reindexing and cannot collide across tenants. `Document` is the logical user-facing asset; `DocumentVersion` records immutable ingestion attempts/content versions for that asset.

`documents.current_version_id` is a real foreign key to `document_versions.id`. SQLAlchemy emits the named constraint in a separate DDL step to handle the circular table dependency cleanly, and `ON DELETE SET NULL` preserves a logical document if its active-version pointer is removed.

## Control-Plane Schema (Tasks 4–11)

The v2 schema defined in `docs/architecture/control-plane.md` is represented in SQLAlchemy metadata. A clean `python -m scripts.create_tables` or `python -m scripts.reset_dev_db` run from `backend/` creates all ten tables.

| Task | Implemented result |
|---|---|
| 4 | `documents.current_version_id` foreign key and `Document.current_version` relationship |
| 5 | `ingestion_runs` pipeline execution/audit table |
| 6 | `chunks` metadata and Qdrant point lineage table; vectors remain outside PostgreSQL |
| 7 | `embedding_runs` progress and model-comparison table |
| 8 | `query_logs` observability/cache/agent-route table |
| 9 | `retrieval_logs` ranked chunk trace table |
| 10 | Shared canonical statuses, ORM validation, and PostgreSQL `CHECK` constraints |
| 11 | Required single-column and high-priority composite indexes |

The schema deliberately separates durable metadata from data-plane storage:

```text
PostgreSQL: identities, paths, statuses, run history, chunk/query/retrieval metadata
MinIO:      Bronze raw objects, Silver chunk Parquet, Gold embedded metadata Parquet
Qdrant:     dense and sparse vectors (PostgreSQL stores qdrant_point_id only)
Redis:      temporary cache, session, progress, and rate-limit state
Airflow:    optional DAG scheduling; ingestion_runs.airflow_dag_run_id provides traceability
Celery:     optional chain/work queue; currently reuses ingestion_runs.airflow_dag_run_id for workflow traceability
```

Status validation is enforced twice: SQLAlchemy rejects invalid values before persistence, and PostgreSQL check constraints protect writes from any other client. Canonical values live in `backend/app/models/statuses.py`.

## Control-Plane Runtime (Tasks 12–23 and 25–27)

Tasks 12–23 add the migration, runtime consumers, deterministic seed data,
database validation, and authenticated real-time delivery:

| Task | Implemented result |
|---|---|
| 12 | Async Alembic environment and reversible `20260711_0001` full-schema migration |
| 13 | Ten SQLAlchemy models matching the migrated PostgreSQL schema |
| 14 | Async repository modules for projects, documents, versions, ingestion, chunks, embeddings, queries, and retrievals |
| 15 | `POST /ingest/file` lands raw bytes in MinIO Bronze and returns an ingestion run with HTTP 202 |
| 16 | `GET /ingest/runs/{ingestion_run_id}` reports durable status and Bronze/Silver/Gold/Qdrant progress |
| 17 | Authenticated internal pipeline API, optional Airflow REST enqueue, Airflow client plugin, and ingestion DAG status boundaries |
| 17C | Celery orchestration boundary, Celery worker app, five-task ingestion chain, and matched Celery benchmark package |
| 18 | Deterministic PostgreSQL/Qdrant chunk lineage, complete tenant/version payloads, idempotent version rebuilds, and an authenticated Gold-chunk indexing boundary |
| 19 | Normalized question hashing, best-effort Redis response caching, and durable provider/model/latency/cache/route query logs |
| 20 | Structured retrieval hits and durable rank, Qdrant score, optional rerank score, strategy, chunk lineage, and answer-usage traces |
| 21 | Idempotent namespaced seed data plus real PostgreSQL relationship, lifecycle, uniqueness, foreign-key, and query-lineage tests |
| 22 | Executable schema introspection for required tables, foreign keys, unique/check constraints, indexes, and Alembic upgrade/rollback validation |
| 23 | Authenticated ingestion SSE snapshots/replay, Redis Stream fan-out with PostgreSQL recovery, shared streaming/non-streaming RAG execution, durable answers, and token/stage events |
| 25 | Container-safe Bronze-to-Silver and Silver-to-Gold Parquet jobs, deterministic Gold-to-Qdrant indexing, durable artifact paths, retries, and failure propagation |
| 26 | Isolated containerized upload-to-answer validation across API, PostgreSQL, MinIO, Airflow, Qdrant, Redis, SSE, provider failures, and tenant boundaries |
| 27 | Next.js authenticated control plane with projects, uploads, durable ingestion recovery/retry, streamed RAG chat, history, and retrieval traces |

The repository layer owns reusable database operations and does not commit implicitly. API routes and pipeline boundaries control transactions, allowing multi-row document/version/run creation to remain atomic.

Task 25 replaces the old orchestration command placeholders with built-in batch jobs and shared stage logic. The Airflow image can run those jobs through configured commands, while the Celery worker calls the shared Python stages directly. Both paths read version metadata through the authenticated internal API, transform MinIO Bronze objects into Silver and Gold Parquet, and send Gold rows through the deterministic Task 18 indexing boundary. Artifact keys are version-scoped and overwritten on retry; PostgreSQL paths and statuses advance only after the corresponding object write succeeds.

Task 26 packages the Airflow-backed complete runtime into a repeatable `make e2e-v2` gate. It uses a separate Compose project and volumes, alternate host ports, a local OpenAI-compatible provider, and deterministic embeddings. Public APIs drive the user flows; direct PostgreSQL, MinIO, Airflow, and Qdrant clients are used only to assert cross-system counts, paths, timestamps, ranks, and lineage. The Celery branch currently adds focused orchestration tests and a matched Celery benchmark runner rather than a full Celery E2E gate.

Task 27 adds a production-built Next.js service. Authentication is exchanged
through Next.js route handlers and stored in an HttpOnly cookie; the browser
never reads the FastAPI JWT. A path-preserving same-origin proxy forwards JSON,
multipart uploads, and streaming SSE responses. Ingestion views reconnect with
`Last-Event-ID` and recover through PostgreSQL status reads. The backend now
also exposes tenant-owned recent runs, safe failed-run retries, query history,
and ranked chunk/document retrieval traces. The public sign-in route is a
focused RAG engineering control-plane entrance: it keeps the real login request,
session cookie, `/projects` redirect, and registration link intact while
presenting the document-to-grounded-answer workflow, retrieval tracing, and
source-aware answer model without adding fake metrics, OAuth, or password
recovery affordances.

Airflow and Celery talk to `GET/PATCH /internal/pipeline/ingestion-runs/{id}` with `PIPELINE_SERVICE_TOKEN`. This HTTP boundary intentionally keeps orchestration workers from owning application database writes directly. The internal API delegates every write to the same ingestion repository used elsewhere. In Airflow mode, FastAPI authenticates through Airflow's `/auth/token` endpoint and triggers DAG runs through the Airflow 3 public `/api/v2` API. In Celery mode, FastAPI publishes a Celery chain through `app/workers/tasks.py`. If the configured orchestrator does not accept a landed run, `backend/app/services/ingestion_orchestrator.py` persists the run as `failed`, records `finished_at`, publishes a failure event, and leaves the deterministic Bronze object available for retry.

The `ragforge_ingestion` DAG runs `detect_ingestion_technique`, `bronze_to_silver`, `silver_to_gold_embed`, `upsert_qdrant`, and `update_postgres_status`. The Celery chain mirrors the same logical boundaries as `detect_ingestion_plan_task`, `bronze_to_silver_task`, `silver_to_gold_task`, `upsert_qdrant_task`, and `finalize_ingestion_task`. The first stage reads durable run/version/document metadata through the control-plane API, receives an `ingestion_plan`, and records the run as `running`. Airflow transformation commands receive `{ingestion_run_id}`, `{profile}`, `{chunker_id}`, and `{source_type}`; Celery tasks call shared Python stage functions in `backend/jobs/ingestion_workflow.py`. The Task 18 indexing boundary accepts embedded Gold chunks at `POST /internal/pipeline/ingestion-runs/{id}/chunks/index`, rebuilds that version's Qdrant points, and atomically replaces its PostgreSQL chunk rows.

### Adaptive ingestion execution

`backend/app/services/ingestion_planner.py` is the single policy layer that translates the persisted `DocumentVersion.chunker_id` and `Document.source_type` into execution hints. `GET /internal/pipeline/ingestion-runs/{id}` includes this plan without requiring a database migration; the decision is recomputed from durable metadata each time.

| Technique | Profile | Resource class | Embedding batch | Max parallelism | Optimization intent |
|---|---|---|---:|---:|---|
| `fixed_size`, `paragraph`, `sentence` | `throughput` | CPU | 192 | 4 | Larger batches for lightweight deterministic chunking |
| `hierarchical` | `structured` | CPU | 96 | 2 | Moderate batches for parent/child expansion |
| `semantic`, `late_chunking` | `embedding_aware` | high-memory CPU | 48 | 1 | Bound memory while a chunking model is already loaded |
| `proposition` | `llm_enriched` | network | 32 | 1 | Serialize rate-limit-sensitive LLM chunking |
| `multimodal` source/technique | `multimodal` | GPU | 2 | 1 | Keep visual multi-vector batches small |

`backend/jobs/ingestion_execution.py` first looks for a profile-specific command such as `RAGFORGE_SILVER_TO_GOLD_EMBEDDING_AWARE_CMD`, then falls back to `RAGFORGE_SILVER_TO_GOLD_CMD` for backward compatibility. It exports the selected plan to worker processes as `RAGFORGE_INGESTION_PROFILE`, `RAGFORGE_INGESTION_TECHNIQUE`, `RAGFORGE_INGESTION_RESOURCE_CLASS`, `RAGFORGE_EMBEDDING_BATCH_SIZE`, `RAGFORGE_EMBEDDING_TIMEOUT_SECONDS`, and `RAGFORGE_INGESTION_MAX_PARALLELISM`.

The built-in Gold transformation consumes the planned embedding batch size instead of embedding every chunk at once. It reports `loading_model`, per-batch `running`, `completed`, and `failed` embedding progress through the internal pipeline API without exposing chunk text or vectors. The `late_chunking` implementation preserves its normalized mean-pooled sentence vectors in Silver Parquet and reuses them in Gold, avoiding a second embedding pass. These are pooled independent sentence embeddings, not token-level vectors from one full-document contextual encoding. Other techniques leave `precomputed_dense_vector` empty and use the normal batched embedder.

Qdrant only accepts unsigned integers or UUIDs as point IDs. RAGForge therefore preserves the readable `{document_version_id}:{chunk_index}` key as `lineage_id` in every payload and derives the actual Qdrant/PostgreSQL `qdrant_point_id` deterministically with UUIDv5. Replaying the same Gold artifact produces the same chunk and point IDs; old points for that document version are removed before the rebuilt set is upserted. Duplicate chunk text/content hashes are allowed and still receive distinct lineage IDs from their chunk indexes.

## Model Package Layout

The model package now follows one table per file:

| Table | Model file |
|---|---|
| `organizations` | `backend/app/models/organization.py` |
| `users` | `backend/app/models/user.py` |
| `projects` | `backend/app/models/project.py` |
| `documents` | `backend/app/models/document.py` |
| `document_versions` | `backend/app/models/document_version.py` |
| `ingestion_runs` | `backend/app/models/ingestion_run.py` |
| `chunks` | `backend/app/models/chunk.py` |
| `embedding_runs` | `backend/app/models/embedding_run.py` |
| `query_logs` | `backend/app/models/query_log.py` |
| `retrieval_logs` | `backend/app/models/retrieval_log.py` |

`backend/app/models/tables.py` imports and re-exports all models to keep existing imports working:

```python
from app.models.tables import (
    Organization, User, Project, Document, DocumentVersion,
    IngestionRun, Chunk, EmbeddingRun, QueryLog, RetrievalLog,
)
```

New code can also import from `app.models`.

## API Surface

Registration, login, the health check, and the chunker catalog are unauthenticated. Other user-facing routes expect a FastAPI bearer JWT; the frontend supplies it through its same-origin HttpOnly-cookie proxy. Internal pipeline routes use a separate bearer service token.

| Area | Endpoints |
|---|---|
| Health | `GET /health` |
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `PATCH /auth/me`, `DELETE /auth/me` |
| Organizations | `POST /organizations/`, `GET /organizations/`, `GET /organizations/{organization_id}`, `PATCH /organizations/{organization_id}`, `DELETE /organizations/{organization_id}` |
| Projects | `POST /projects/`, `GET /projects/`, `GET /projects/{project_id}`, `PATCH /projects/{project_id}`, `DELETE /projects/{project_id}` |
| Documents | `GET /documents/?project_id=...`, `GET /documents/{document_id}`, `GET /documents/{document_id}/versions`, `DELETE /documents/{document_id}` |
| Chunkers | `GET /chunkers` |
| Ingestion | `POST /ingest/file` (HTTP 202), `GET /ingest/runs?project_id=...`, `GET /ingest/runs/{id}`, `POST /ingest/runs/{id}/retry`, `GET /ingest/runs/{id}/events` (SSE), `POST /ingest/url`, `POST /ingest/gdrive`, `POST /ingest/multimodal` |
| Query | `POST /rag/query`, `POST /rag/query/stream` (SSE), `POST /rag/multimodal-query`, `GET /rag/projects/{project_id}/history`, `GET /rag/queries/{query_log_id}` |
| Pipeline internal | `GET/PATCH /internal/pipeline/ingestion-runs/{id}`, `POST /internal/pipeline/ingestion-runs/{id}/chunks/index` |

### Backend capability boundaries

| Domain | Supported | Not currently supported |
|---|---|---|
| Projects | Create, owner-scoped list/read, rename, soft delete, stable UUID collection name | Description, default chunker, advanced project settings, status/count/activity aggregates |
| Documents | Project list, read, version list, soft delete, new version through re-upload | Update metadata, read one version by ID, rollback, delete one version, direct chunk editing |
| Ingestion runs | Project list, read, failed-run retry, SSE snapshot/replay/recovery | Cancel endpoint, retry history, per-stage duration/timestamp records, structured diagnostics |
| Queries | Synchronous/streaming answer, document filter, provider/model choice, history, ranked trace | Regenerate endpoint, feedback endpoint, structured citations in the answer response |
| Organizations | Authenticated create/list/read/rename/soft delete | Membership roles, admin authorization, per-user organization scoping |

Project tenancy is enforced by `Project.created_by`, not by organization membership. Organization endpoints currently expose every non-deleted organization to any authenticated user. A project create/update payload only supports `name` plus optional `organization_id` on create.

`DocumentVersion` is exposed only through `GET /documents/{document_id}/versions`. Query responses return `query_log_id` and optionally bare `retrieved_chunks`; linked document/version/rank/score details require the follow-up query-trace endpoint. Fully linked traces are available only for points that have PostgreSQL `Chunk` lineage.

### Lifecycle contract

```text
Document:
uploaded | landed | processing | chunked | embedded | indexed | failed | deleted

IngestionRun:
landed -> queued -> running -> silver_completed -> gold_completed -> indexed
any non-terminal stage -> failed | cancelled

EmbeddingRun:
queued -> loading_model -> running -> completed
any non-terminal stage -> failed | cancelled
retrying may be recorded between attempts when a worker reports a retry
```

Only failed runs can be retried. Retry resets the run to `queued`, clears its timing/error/orchestration ID and Silver/Gold paths, and returns the document/version to `landed`. Public run reads reconcile stale `landed` or `queued` runs that exceeded `INGESTION_DISPATCH_TIMEOUT_SECONDS` by marking them `failed`, recording `finished_at`, and preserving the Bronze artifact for safe retry.

The public run response exposes four coarse progress booleans (`bronze`, `silver`, `gold`, `qdrant`) plus run-level timestamps, error text, and optional `embedding_progress` derived from `embedding_runs`. Embedding progress stores real chunk and batch counters, model/backend/device/dimension metadata, attempt number, heartbeat, and safe errors. Redis/SSE maps the six forward statuses to ordered progress events, allows same-status `running` embedding heartbeats, and also emits terminal failure/cancellation events. PostgreSQL does not currently store nine separate pipeline-stage records.
The onboarding progress UI treats `progress.bronze` as the durable Bronze
completion signal and shows `landed`/`queued` runs as waiting for parsing rather
than as an active Bronze upload.

## Docker And Local Services

Default `docker compose up -d --build` services:

| Service | Role |
|---|---|
| `postgres` | Main application PostgreSQL database |
| `qdrant` | Vector database for dense, sparse, and optional multivector search |
| `minio` | Local S3-compatible object storage |
| `minio-init` | Creates local buckets through `scripts/init_minio.sh` |
| `redis` | Best-effort query cache plus short-lived ingestion event replay/fan-out |
| `fastapi` | Backend app built from `backend/Dockerfile` |
| `frontend` | Next.js control-plane UI and authenticated same-origin proxy |

The FastAPI container uses `/app` as its working directory, mounts `./backend:/app` for development reloads, installs `backend/requirements.txt`, and starts with:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Airflow profile services, enabled with `--profile airflow`, add the Airflow 3.3 API server/new UI, scheduler, standalone DAG processor, triggerer, metadata database, and Spark. They use the custom `backend/airflow/Dockerfile`, which adds the parser, PyArrow, FastEmbed, and MinIO dependencies used by Task 25. The local stack keeps `LocalExecutor`.

Celery profile services, enabled with `--profile celery`, add `celery-worker`, which runs `celery -A app.workers.celery_app:celery_app worker --loglevel=INFO` against the same FastAPI, PostgreSQL, MinIO, Qdrant, and Redis services. Use `ORCHESTRATOR=celery` and a shared `PIPELINE_SERVICE_TOKEN` so FastAPI and the worker agree on the internal pipeline token.

The built-in Bronze-to-Silver job is Python/PyArrow, not Spark. The Compose Spark service is available to profile-specific external commands but is not used by the default in-repository job. Migrations are not run by FastAPI startup or the image entry point; deployments must run Alembic separately. `GET /health` is process-only and does not probe PostgreSQL, Qdrant, MinIO, Redis, Airflow, or Celery.

## Requirements Strategy

`backend/requirements.txt` is intentionally a slim default runtime set. It includes FastAPI, SQLAlchemy/asyncpg, Qdrant, FastEmbed, Celery, the async Redis client, document parsers, auth, OpenAI/Groq clients, and S3/R2 support. MinIO clients use `MINIO_CONNECT_TIMEOUT_SECONDS`, `MINIO_READ_TIMEOUT_SECONDS`, and `MINIO_MAX_ATTEMPTS` to keep S3 operations bounded.

It intentionally does not include older full frozen-environment dependencies or heavy optional stacks such as PyTorch/CUDA wheels, `sentence-transformers`, `transformers`, `colpali_engine`, LangChain, and evaluation/training packages.

Optional ColQwen2/`colpali_engine` multimodal support and CrossEncoder reranking should be added through a separate image, profile, or extras file if they are needed.

## File Ingestion Flow

1. The user authenticates with JWT.
2. The API verifies project ownership.
3. The API validates the file/chunker, hashes content, and gets or creates a logical `Document`.
4. Raw bytes are stored under the versioned path in the MinIO `bronze` bucket after validating that the bucket exists.
5. One transaction creates `DocumentVersion(status=landed)` and `IngestionRun(status=landed)`.
6. The API returns HTTP 202 with document, version, and ingestion-run IDs; it does not parse/embed/index in the request.
7. When orchestration is configured, a post-response task calls `backend/app/services/ingestion_orchestrator.py`; `ORCHESTRATOR=airflow` triggers the Airflow DAG, and `ORCHESTRATOR=celery` publishes the Celery chain. Enqueue failures are terminal and retryable instead of being silently logged while the run remains landed/queued.
8. The selected orchestrator fetches run metadata and detects the ingestion technique from the persisted chunker/source, producing a deterministic execution profile.
9. Airflow can use profile-specific commands when configured; Celery calls the shared stage functions directly.
10. The selected orchestrator parses/chunks Bronze into Silver Parquet, records embedding model preparation/progress through `embedding_runs`, embeds Silver in planner-sized batches into Gold Parquet, and indexes Gold through the internal Qdrant boundary. Pooled Sentence Chunking reuses vectors computed during chunk construction.
11. PostgreSQL advances at `running`, `silver_completed`, `gold_completed`, and `indexed` only after each data-plane boundary succeeds; failures durably store their error.

URL and Google Drive ingestion fetch, parse, chunk, embed, and index inside the request, then create an already-indexed version. They do not create `IngestionRun` or PostgreSQL `Chunk` rows, so their retrieval logs cannot resolve complete chunk/document/version lineage. Their version path fields are metadata placeholders rather than written Bronze/Silver/Gold artifacts.

Multimodal ingestion is also synchronous. It renders a bounded PDF into page images, creates ColQwen2 multi-vectors, uploads images to R2, and writes a separate `<project_collection>_multimodal` collection. It creates an indexed version but no ingestion run or PostgreSQL chunks.

## Document Versioning

Document versioning is currently metadata-first:

- Re-uploading the same filename/source in the same project updates the existing logical `Document`.
- A new content hash creates the next `DocumentVersion`.
- Re-uploading identical content for the same document returns `409`.
- `Document.current_version_id` points to the latest successful version.
- Version rows store lineage paths for bronze/silver/gold artifacts, parser, chunker, embedding model, status, and errors.
- Only durable file ingestion guarantees that the stored artifact paths correspond to objects written in MinIO.

The API currently lists versions with:

```text
GET /documents/{document_id}/versions
```

There is no separate route for reading one version by ID, rolling back to an older version, or deleting a single version yet.

## Chunking System

The chunker registry is the single source of truth. It exposes product metadata for frontends through `GET /chunkers` and validates ingestion requests.

Public chunkers:

| ID | Product Name | Tier | Status | Runtime Notes |
|---|---|---|---|---|
| `fixed_size` | Starter Chunking | base | stable | Bounded character windows with configurable character overlap |
| `paragraph` | Base Chunking | base | stable | Default; packs paragraphs and splits only oversized paragraphs into overlapping word windows |
| `sentence` | Precision Chunking | pro | stable | Sentence-aligned groups; merges short fragments; NLTK with regex fallback |
| `semantic` | Semantic Chunking | pro | beta | Splits on adjacent-sentence embedding similarity; no overlap |
| `hierarchical` | Structured Chunking | business | beta | Deterministic sentence-count parent/child groups; not heading/layout aware |
| `late_chunking` | Pooled Sentence Chunking | ultimate | beta | Mean-pools independent sentence embeddings; not token-level full-document late chunking |
| `proposition` | Ultimate Chunking | ultimate | beta | Uses Groq when `GROQ_API_KEY` is configured, falls back per paragraph on errors |
| `multimodal` | Multimodal Chunking | ultimate | experimental | PDF page rendering and ColQwen2 multi-vectors; requires the optional heavy runtime and R2 |

`registry.py` uses lazy callable paths so listing metadata does not import heavy chunker implementations. Text ingestion rejects `multimodal`; that mode belongs to `/ingest/multimodal`.

The detailed implementation-level capability map lives in `backend/app/services/chunkers/chuncker_map.md`.

## Retrieval And Generation

Text RAG query flow:

```text
question
  -> normalize/hash + optional Redis cache lookup
  -> durable QueryLog
  -> FastEmbed BGE query embedding
  -> Qdrant hybrid dense+sparse search
  -> optional rerank with structured scores
  -> durable RetrievalLog rows
  -> context prompt
  -> Gemini or Groq OpenAI-compatible chat completion
  -> optional stage/token SSE events
  -> mark used chunks + persist/cache response + answer
```

Redis cache failures degrade to a normal retrieval/generation request. Cache
state is recorded in PostgreSQL, which remains the durable source of truth.
Cache keys include the project, normalized question, provider/model, optional
document filter, and parent-context flag. They do not include an index/version
generation, and ingestion/deletion does not invalidate cache entries; freshness
therefore depends on `QUERY_CACHE_TTL_SECONDS`.

Task 23 uses Redis Streams only as a short replay/fan-out layer. Every ingestion
subscription begins with the current PostgreSQL snapshot, accepts
`Last-Event-ID`, filters duplicate sequences, emits heartbeats, and falls back
to durable polling when Redis is unavailable. Streaming queries run in an
independent database session so client disconnects do not cancel query and
retrieval logging.

Query streaming uses an in-process queue and is not replayable. It emits
received, embedding, retrieving, reranking, generation, token, completion, and
failure events. The worker retains its own database session so browser
disconnects do not cancel provider work or durable logging.

Optional query controls:

- `document_id` filters retrieval to one document.
- `use_parent_context` expands hierarchical child hits to parent context.
- `include_context` returns retrieved chunks for debugging/trusted clients.

Reranking behavior:

- If `sentence-transformers` is installed, `backend/app/services/retrieval/rerank.py` lazily loads `cross-encoder/ms-marco-MiniLM-L-6-v2`.
- If it is not installed, reranking degrades to the current Qdrant hybrid order rather than failing the backend import.

Optional multimodal query flow:

```text
question
  -> ColQwen query vectors
  -> Qdrant multivector page search
  -> page image URLs from R2/S3 storage
  -> Gemini vision response
```

The multimodal flow requires the optional ColQwen2/`colpali_engine` stack and R2/S3 settings. Those packages are not part of the slim default Docker image.

## Configuration

Core settings:

- `DATABASE_URL`
- `SECRET_KEY`
- `QDRANT_URL`
- `QDRANT_API_KEY`
- `EMBEDDING_BACKEND` (`fastembed` by default; `deterministic` for offline tests)
- `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`, `EMBEDDING_DEVICE`
- `EMBEDDING_BATCH_SIZE`, `EMBEDDING_TIMEOUT_SECONDS`
- `EMBEDDING_ALLOW_MODEL_DOWNLOAD`, `EMBEDDING_CACHE_DIR`
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`
- `MINIO_BUCKET_BRONZE`, `MINIO_BUCKET_SILVER`, `MINIO_BUCKET_GOLD`
- `REDIS_URL`
- `QUERY_CACHE_TTL_SECONDS`
- `MAX_UPLOAD_BYTES`
- `MAX_MULTIMODAL_PAGES`
- `DEBUG_RETURN_CONTEXT`
- `EVENT_STREAM_MAXLEN`
- `EVENT_STREAM_TTL_SECONDS`
- `SSE_HEARTBEAT_SECONDS`
- `SSE_POLL_SECONDS`
- `ORCHESTRATOR` selects `airflow` or `celery` for durable file ingestion
- `AIRFLOW_API_URL`, `AIRFLOW_USERNAME`, `AIRFLOW_PASSWORD`, `AIRFLOW_INGESTION_DAG_ID` for optional DAG submission from FastAPI
- `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `CELERY_TASK_ALWAYS_EAGER`, `CELERY_WORKER_PREFETCH_MULTIPLIER`, `CELERY_TASK_RETRY_DELAY_SECONDS`, `CELERY_TASK_MAX_RETRIES` for Celery workers
- `PIPELINE_SERVICE_TOKEN` for Airflow/Celery-to-FastAPI internal pipeline calls
- `RAGFORGE_BRONZE_TO_SILVER_CMD`, `RAGFORGE_SILVER_TO_GOLD_CMD`, `RAGFORGE_UPSERT_QDRANT_CMD` for generic pipeline jobs
- `RAGFORGE_<STAGE>_<PROFILE>_CMD` for optional Airflow profile-specific worker backends, where the profile suffix is `THROUGHPUT`, `STRUCTURED`, `EMBEDDING_AWARE`, `LLM_ENRICHED`, or `MULTIMODAL`

Optional provider settings:

- `GEMINI_API_KEY` for Gemini queries.
- `GROQ_API_KEY` for Groq queries and proposition chunking.
- `GEMINI_BASE_URL`, `GROQ_BASE_URL`, `LLM_MAX_RETRIES`, `LLM_TIMEOUT_SECONDS` for OpenAI-compatible provider clients.
- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_URL` for multimodal page image storage.

`DATABASE_URL`, `SECRET_KEY`, and `QDRANT_URL` are required at settings import time. Docker Compose passes most runtime settings from the shell environment and hardcodes service URLs for local containers.

## Development Utilities

| File | Purpose |
|---|---|
| `backend/BACKEND_MAP.md` | Detailed code-level backend request, storage, lifecycle, and ownership map |
| `backend/Dockerfile` | Builds the default FastAPI runtime image from slim requirements |
| `backend/.dockerignore` | Prevents local `.venv`, caches, `.env`, and Airflow logs from entering the image |
| `backend/requirements.txt` | Slim runtime dependency list for default backend, including Celery |
| `frontend/Dockerfile` | Builds the standalone Next.js control-plane image |
| `docker-compose.yml` | Starts Next.js, Postgres, Qdrant, MinIO, Redis, FastAPI, and optional `airflow` / `celery` profiles |
| `scripts/init_minio.sh` | Creates local MinIO buckets |
| `backend/alembic.ini`, `backend/alembic/` | Reversible production schema migration and autogenerate metadata integration |
| `backend/scripts/create_tables.py` | Legacy/development helper for creating missing tables directly from metadata |
| `backend/scripts/reset_dev_db.py` | Destructively deletes Qdrant collections and rebuilds DB tables |
| `backend/scripts/seed_control_plane.py` | Idempotently creates one complete namespaced control-plane graph |
| `backend/scripts/validate_control_plane.py` | Introspects the migrated database and reports the Task 22 structural checklist |
| `backend/scripts/check_data.py` | Helper for inspecting indexed Qdrant data |
| `backend/scripts/cleanup.py` | Helper for deleting document chunks from Qdrant |
| `test_chunkers.sh` | End-to-end smoke test using `Rapport_de_stage_bac+3.pdf` |
| `backend/tests/unit/chunking/test_chunker_registry.py` | Registry metadata and lightweight import tests |
| `backend/tests/unit/chunking/test_chunkers_api.py` | `/chunkers` and invalid chunker API tests when FastAPI is installed |
| `backend/tests/unit/models/test_auth_validation.py` | Registration/profile validation and organization-reference checks |
| `backend/tests/unit/api/test_frontend_control_plane_api.py` | Frontend-facing organization, project, and document API behavior |
| `backend/tests/unit/embeddings/test_embedding_backends.py` | FastEmbed selection and deterministic offline embedding behavior |
| `backend/tests/unit/models/test_control_plane_models.py` | Tasks 4–11 table, foreign-key, status, uniqueness, and composite-index tests |
| `backend/tests/integration/postgres/test_control_plane_database.py` | Tasks 21–22 isolated PostgreSQL seed, constraint, relationship, lifecycle, schema, and migration tests |
| `backend/tests/integration/postgres/test_control_plane_runtime.py` | Repository transitions, retry/recovery, seeding, and schema-validation behavior |
| `backend/tests/integration/streaming/test_realtime_streaming.py` | Task 23 SSE, replay, fallback, ownership, token, disconnect, heartbeat, and optional live Redis tests |
| `backend/tests/unit/ingestion/test_pipeline_artifacts.py` | Task 25 deterministic Silver/Gold Parquet, retry, empty input, and embedding mismatch tests |
| `backend/tests/unit/ingestion/test_bronze_storage.py` | Bronze MinIO bucket validation, bounded upload boundary, and idempotent object-key behavior |
| `backend/tests/unit/ingestion/test_ingestion_planner.py` | Adaptive technique classification, profiles, resource classes, batch sizes, and concurrency hints |
| `backend/tests/unit/ingestion/test_ingestion_execution.py` | Profile-specific command selection, generic fallback, and worker environment propagation |
| `backend/tests/integration/airflow/test_airflow_service.py` | Airflow REST authentication, DAG trigger, and durable run-ID handling |
| `backend/tests/integration/celery/test_celery_orchestration.py` | Orchestrator selection, Celery enqueue behavior, shared stage transitions, and worker entry-point loading |
| `backend/tests/benchmarks/test_airflow_benchmark.py` | Airflow benchmark workload, validation, metric, and timestamp handling tests |
| `backend/tests/benchmarks/test_celery_benchmark.py` | Celery benchmark workload, validation, metric, and timestamp handling tests |
| `backend/tests/integration/qdrant/test_qdrant_chunk_lineage.py` | Deterministic point/chunk identity and idempotent version indexing |
| `backend/tests/unit/api/test_rag_observability.py` | Query/retrieval logging, Redis cache behavior, and structured retrieval hits |
| `backend/tests/e2e/test_control_plane.py` | Task 26 Airflow-backed containerized upload-to-answer, lineage, Redis recovery, failure, and tenant-isolation tests |
| `scripts/e2e_v2.sh` | Isolated one-command Task 26 Compose orchestrator |
| `frontend/src/**/*.test.tsx` | Task 27 loading, empty, success, failure, SSE parsing, and reconnect tests |
| `frontend/src/app/(auth)/login/page.test.tsx` | Focused sign-in UX/auth tests for validation, pending submit state, accessible backend errors, password visibility, and the unchanged `/api/auth/login` flow |
| `.github/workflows/frontend.yml` | Frontend lint, test, and production-build gate |
| `backend/evaluation/legacy/evaluate_legacy_ragas.py` | Legacy evaluation helper for local experiments |
| `backend/evaluation/airflow_benchmark/` | Airflow benchmark CLI and report package |
| `backend/evaluation/celery_benchmark/` | Celery benchmark CLI and report package |

## Current Design Notes

- Alembic is the production schema path. Revision `20260711_0001` upgrades an empty database to the full schema and downgrades cleanly; `backend/scripts/create_tables.py` remains a development compatibility helper.
- Qdrant is the vector store; Postgres stores control-plane ownership, version/run lineage, chunk metadata, and query/retrieval audit metadata.
- FastEmbed handles both default dense embeddings and BM25 sparse vectors.
- R2/S3 storage is used only for optional multimodal PDF page images.
- The text ingestion endpoint rejects the `multimodal` chunker because multimodal has its own endpoint.
- Adaptive plans are execution hints, not a scheduler by themselves. The generic commands work unchanged; profile-specific command variables can route work to optimized CPU, high-memory, network-bound, or GPU backends.
- The planner is derived from durable chunker/source metadata and adds no control-plane table or migration.
- Pooled-sentence (`late_chunking`) vectors cross the Silver/Gold boundary as `precomputed_dense_vector`; other chunkers are embedded in batches selected by the planner.
- The registry is built for SaaS frontend display and does not expose callable paths publicly.
- The default Docker image is intentionally text-RAG focused; optional multimodal and CrossEncoder rerank dependencies should be isolated.
- `EmbeddingRun` has a model and repository but the active API/orchestrator pipeline does not create or update embedding-run records.
- Document deletion removes base-collection text points and R2 images, but it does not explicitly remove that document's points from the multimodal collection. Project deletion removes both entire collections.
- Qdrant and PostgreSQL writes are not atomic. Deterministic IDs and version replacement make retry/rebuild the recovery path.
- Orchestrator triggering is optional and best-effort. Without a configured selected orchestrator, a file upload remains `landed`; there is no inline pipeline fallback.
- When a selected Airflow or Celery orchestrator is configured but fails to accept a run, the run is marked `failed` with `finished_at` so the frontend can show a safe retry instead of an indefinite Bronze/queued state.
- Celery currently reuses the existing `ingestion_runs.airflow_dag_run_id` column for workflow IDs to avoid schema churn during comparison.
- The containerized E2E suite is still Airflow-oriented; Celery currently has focused unit tests and benchmark validation.
- `app/main.py` has no CORS middleware or startup dependency checks.
- The frontend uses a same-origin Next.js proxy so JWTs remain in HttpOnly
  cookies while authenticated POST and GET SSE streams retain header-based
  FastAPI authorization.
- The redesigned login page uses the black/charcoal/warm-cream interface
  palette, a compact ingest/retrieve/observe workflow, an elevated sign-in
  panel, accessible inline authentication errors, keyboard-friendly password
  visibility, and dark autofill styling. Registration is linked because
  `/register` exists; password recovery and OAuth are intentionally omitted
  because no matching auth routes are implemented.
