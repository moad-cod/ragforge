# RAGForge Project Map

RAGForge is a FastAPI SaaS backend for authenticated, multi-tenant Retrieval-Augmented Generation. It ingests files and web sources, versions document content, chunks and embeds text, stores dense and sparse vectors in Qdrant, and answers questions through OpenAI-compatible LLM providers. PostgreSQL also defines the durable v2 control plane for ingestion runs, chunk lineage, embedding runs, query history, and retrieval traces.

The default backend is optimized for the text RAG path. Heavy optional features such as ColPali multimodal ingestion and CrossEncoder reranking are kept out of the default runtime requirements so Docker builds stay practical.

## Architecture

```text
Client / Swagger UI
  -> FastAPI routers
  -> Auth / Organizations / Projects / Documents / Chunkers / Ingest / Query
  -> SQLAlchemy async + PostgreSQL control-plane metadata
  -> Parser + chunker registry + embedding services
  -> FastEmbed dense BGE vectors + FastEmbed BM25 sparse vectors
  -> Qdrant dense+sparse vector collections
  -> Hybrid retrieval + optional reranking
  -> Gemini or Groq chat completion
```

## Main Runtime Modules

| Area | Files | Responsibility |
|---|---|---|
| App entry | `backend/app/main.py` | Creates the FastAPI app and mounts routers |
| Config | `backend/app/core/config.py` | Loads `.env`, required URLs/secrets, optional LLM/R2 settings, limits |
| Auth | `backend/app/core/auth.py`, `backend/app/api/auth.py` | JWT dependency, register, login, current-user read/update/delete |
| Database | `backend/app/core/db.py` | Async SQLAlchemy engine, session dependency, declarative `Base` |
| Models | `backend/app/models/*.py` | One SQLAlchemy model per control-plane table, relationships, constraints, and indexes; `tables.py` remains a compatibility export |
| Organizations | `backend/app/api/organizations.py` | Organization CRUD and soft delete |
| Projects | `backend/app/api/projects.py` | Project CRUD, ownership checks, Qdrant collection lifecycle |
| Documents | `backend/app/api/documents.py` | Document list/get/delete and document version listing |
| Ingestion | `backend/app/api/ingest.py` | File, URL, Google Drive, and optional multimodal ingestion |
| Query | `backend/app/api/query.py` | Text RAG query and optional multimodal page query |
| Chunker catalog | `backend/app/api/chunkers.py`, `backend/app/services/chunkers/registry.py` | Public chunker metadata, validation, and lazy callable lookup |
| Parsing | `backend/app/services/parser.py` | PDF, DOCX, XLSX, PPTX, CSV, HTML, text, URL, and Google Drive parsing |
| Dense embeddings | `backend/app/services/embedder.py` | Lazy `BAAI/bge-small-en-v1.5` embeddings through FastEmbed |
| Indexing | `backend/app/services/indexer.py` | Qdrant collection creation, upsert, document delete, collection delete |
| Retrieval | `backend/app/services/retriever.py`, `backend/app/services/retrieval/*` | Dense/sparse hybrid search, BM25 sparse embeddings, optional reranking |
| Storage | `backend/app/services/storage.py` | Lazy Cloudflare R2/S3-compatible client for multimodal page images |

## Repository Structure

```text
backend/
  Dockerfile
  .dockerignore
  requirements.txt
  app/
    api/
      auth.py
      chunkers.py
      documents.py
      ingest.py
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
      event_stream.py
      query_cache.py
      query_observability.py
      pipeline_status.py
  jobs/
    bronze_to_silver.py
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
  alembic.ini
  create_tables.py
  reset_dev_db.py
  check_data.py
  cleanup.py
  tests/
Data-Modeling/
  ControlPlane.md
  Tables.png
  design.png
  lifecyvle.png
documents/
  Pdf/
scripts/
  init_minio.sh
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
  created_by, created_at
  belongs to Project, Document, DocumentVersion, and creator User

Chunk
  id, project_id, document_id, document_version_id, ingestion_run_id
  qdrant_point_id, chunk_index, text, content_hash, token/page metadata
  metadata_json, created_at
  belongs to Project, Document, DocumentVersion, and optional IngestionRun

EmbeddingRun
  id, project_id, document_version_id, embedding_model, status
  total_chunks, embedded_chunks, timestamps, error_message
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

The v2 schema defined in `Data-Modeling/ControlPlane.md` is represented in SQLAlchemy metadata. A clean `create_tables.py` or `reset_dev_db.py` run creates all ten tables.

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
Airflow:    pipeline scheduling; ingestion_runs.airflow_dag_run_id provides traceability
```

Status validation is enforced twice: SQLAlchemy rejects invalid values before persistence, and PostgreSQL check constraints protect writes from any other client. Canonical values live in `backend/app/models/statuses.py`.

## Control-Plane Runtime (Tasks 12–23 and 25)

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
| 18 | Deterministic PostgreSQL/Qdrant chunk lineage, complete tenant/version payloads, idempotent version rebuilds, and an authenticated Gold-chunk indexing boundary |
| 19 | Normalized question hashing, best-effort Redis response caching, and durable provider/model/latency/cache/route query logs |
| 20 | Structured retrieval hits and durable rank, Qdrant score, optional rerank score, strategy, chunk lineage, and answer-usage traces |
| 21 | Idempotent namespaced seed data plus real PostgreSQL relationship, lifecycle, uniqueness, foreign-key, and query-lineage tests |
| 22 | Executable schema introspection for required tables, foreign keys, unique/check constraints, indexes, and Alembic upgrade/rollback validation |
| 23 | Authenticated ingestion SSE snapshots/replay, Redis Stream fan-out with PostgreSQL recovery, shared streaming/non-streaming RAG execution, durable answers, and token/stage events |
| 25 | Container-safe Bronze-to-Silver and Silver-to-Gold Parquet jobs, deterministic Gold-to-Qdrant indexing, durable artifact paths, retries, and failure propagation |

The repository layer owns reusable database operations and does not commit implicitly. API routes and pipeline boundaries control transactions, allowing multi-row document/version/run creation to remain atomic.

Task 25 replaces the Airflow command placeholders with built-in batch jobs.
The custom Airflow image reads version metadata through the authenticated
internal API, transforms MinIO Bronze objects into Silver and Gold Parquet,
and sends Gold rows through the deterministic Task 18 indexing boundary.
Artifact keys are version-scoped and overwritten on retry; PostgreSQL paths
and statuses advance only after the corresponding object write succeeds.

Airflow talks to `GET/PATCH /internal/pipeline/ingestion-runs/{id}` with `PIPELINE_SERVICE_TOKEN`. This HTTP boundary intentionally keeps the application database runtime out of Airflow 3.3 task processes. The internal API delegates every write to the same ingestion repository used elsewhere. FastAPI authenticates through Airflow's `/auth/token` endpoint and triggers DAG runs through the Airflow 3 public `/api/v2` API.

The `ragforge_ingestion` DAG exposes the Task 17 sequence (`validate_bronze`, `bronze_to_silver_spark`, `silver_to_gold_embed`, `upsert_qdrant`, `update_postgres_status`). Transformation commands are configured through environment variables and receive `{ingestion_run_id}`; a missing command fails the run instead of falsely advancing its durable status. The Task 18 indexing boundary accepts embedded Gold chunks at `POST /internal/pipeline/ingestion-runs/{id}/chunks/index`, rebuilds that version's Qdrant points, and atomically replaces its PostgreSQL chunk rows.

Qdrant only accepts unsigned integers or UUIDs as point IDs. RAGForge therefore preserves the readable `{document_version_id}:{chunk_index}` key as `lineage_id` in every payload and derives the actual Qdrant/PostgreSQL `qdrant_point_id` deterministically with UUIDv5. Replaying the same Gold artifact produces the same chunk and point IDs; old points for that document version are removed before the rebuilt set is upserted.

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

| Area | Endpoint |
|---|---|
| Health | `GET /health` |
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `PATCH /auth/me`, `DELETE /auth/me` |
| Organizations | `POST /organizations/`, `GET /organizations/`, `GET /organizations/{organization_id}`, `PATCH /organizations/{organization_id}`, `DELETE /organizations/{organization_id}` |
| Projects | `POST /projects/`, `GET /projects/`, `GET /projects/{project_id}`, `PATCH /projects/{project_id}`, `DELETE /projects/{project_id}` |
| Documents | `GET /documents/?project_id=...`, `GET /documents/{document_id}`, `GET /documents/{document_id}/versions`, `DELETE /documents/{document_id}` |
| Chunkers | `GET /chunkers` |
| Ingest | `POST /ingest/file` (HTTP 202 Bronze landing), `GET /ingest/runs/{ingestion_run_id}`, `GET /ingest/runs/{ingestion_run_id}/events` (SSE), `POST /ingest/url`, `POST /ingest/gdrive`, `POST /ingest/multimodal` |
| Query | `POST /rag/query`, `POST /rag/query/stream` (SSE), `POST /rag/multimodal-query` |
| Pipeline internal | `GET/PATCH /internal/pipeline/ingestion-runs/{ingestion_run_id}` and `POST /internal/pipeline/ingestion-runs/{ingestion_run_id}/chunks/index` with service token |

`DocumentVersion` is intentionally exposed through `GET /documents/{document_id}/versions`, not as a separate top-level `/document-versions` router. That keeps versions scoped under their parent document and enforces document ownership before listing version metadata.

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

The FastAPI container uses `/app` as its working directory, mounts `./backend:/app` for development reloads, installs `backend/requirements.txt`, and starts with:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Batch profile services, enabled with `--profile batch`, add the Airflow 3.3 API server/new UI, scheduler, standalone DAG processor, triggerer, metadata database, and Spark. They use the custom `backend/airflow/Dockerfile`, which adds the parser, PyArrow, FastEmbed, and MinIO dependencies used by Task 25. The local stack keeps `LocalExecutor`; the new UI does not require the heavier Celery worker topology.

## Requirements Strategy

`backend/requirements.txt` is intentionally a slim default runtime set. It includes FastAPI, SQLAlchemy/asyncpg, Qdrant, FastEmbed, the async Redis client, document parsers, auth, OpenAI/Groq clients, and S3/R2 support.

It intentionally does not include older full frozen-environment dependencies or heavy optional stacks such as PyTorch/CUDA wheels, `sentence-transformers`, `transformers`, `colpali_engine`, LangChain, and evaluation/training packages.

Optional multimodal ColPali and CrossEncoder reranking should be added through a separate image, profile, or extras file if they are needed.

## File Ingestion Flow

1. The user authenticates with JWT.
2. The API verifies project ownership.
3. The API validates the file/chunker, hashes content, and gets or creates a logical `Document`.
4. Raw bytes are stored under the versioned path in the MinIO `bronze` bucket.
5. One transaction creates `DocumentVersion(status=landed)` and `IngestionRun(status=landed)`.
6. The API returns HTTP 202 with document, version, and ingestion-run IDs; it does not parse/embed/index in the request.
7. When `AIRFLOW_API_URL` is configured, a post-response task triggers `ragforge_ingestion` and records its DAG-run ID/status as `queued`.
8. Airflow parses/chunks Bronze into Silver Parquet, embeds Silver into Gold Parquet, and indexes Gold through the internal Qdrant boundary.
9. PostgreSQL advances at `running`, `silver_completed`, `gold_completed`, and `indexed` only after each data-plane boundary succeeds; failures durably store their command error.

URL, Google Drive, and optional multimodal endpoints retain their existing synchronous implementation for now. Heavy operations on those paths remain offloaded with `asyncio.to_thread` where applicable.

## Document Versioning

Document versioning is currently metadata-first:

- Re-uploading the same filename/source in the same project updates the existing logical `Document`.
- A new content hash creates the next `DocumentVersion`.
- Re-uploading identical content for the same document returns `409`.
- `Document.current_version_id` points to the latest successful version.
- Version rows store lineage paths for bronze/silver/gold artifacts, parser, chunker, embedding model, status, and errors.

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
| `fixed_size` | Starter Chunking | base | stable | Lightweight text split |
| `paragraph` | Base Chunking | base | stable | Default text chunker |
| `sentence` | Precision Chunking | pro | stable | Uses NLTK sentence tokenization when data is available |
| `semantic` | Semantic Chunking | pro | beta | Uses dense embeddings to compare adjacent sentences |
| `hierarchical` | Structured Chunking | business | beta | Creates parent/child chunks for expanded context |
| `late_chunking` | Late Interaction Chunking | ultimate | beta | Groups sentence embeddings and stores pooled vectors |
| `proposition` | Ultimate Chunking | ultimate | beta | Uses Groq when `GROQ_API_KEY` is configured, falls back per paragraph on errors |
| `multimodal` | Multimodal Chunking | ultimate | experimental | Optional heavy path; requires ColPali/ColQwen dependencies not in default requirements |

`registry.py` uses lazy callable paths so listing metadata does not import heavy chunker implementations. Text ingestion rejects `multimodal`; that mode belongs to `/ingest/multimodal`.

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

Task 23 uses Redis Streams only as a short replay/fan-out layer. Every ingestion
subscription begins with the current PostgreSQL snapshot, accepts
`Last-Event-ID`, filters duplicate sequences, emits heartbeats, and falls back
to durable polling when Redis is unavailable. Streaming queries run in an
independent database session so client disconnects do not cancel query and
retrieval logging.

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

The multimodal flow requires the optional ColPali/ColQwen stack and R2/S3 settings. Those packages are not part of the slim default Docker image.

## Configuration

Core settings:

- `DATABASE_URL`
- `SECRET_KEY`
- `QDRANT_URL`
- `QDRANT_API_KEY`
- `REDIS_URL`
- `QUERY_CACHE_TTL_SECONDS`
- `MAX_UPLOAD_BYTES`
- `MAX_MULTIMODAL_PAGES`
- `DEBUG_RETURN_CONTEXT`
- `EVENT_STREAM_MAXLEN`
- `EVENT_STREAM_TTL_SECONDS`
- `SSE_HEARTBEAT_SECONDS`
- `SSE_POLL_SECONDS`

Optional provider settings:

- `GEMINI_API_KEY` for Gemini queries.
- `GROQ_API_KEY` for Groq queries and proposition chunking.
- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_URL` for multimodal page image storage.

Docker Compose passes most runtime settings from the shell environment and hardcodes service URLs for local containers. `SECRET_KEY` is required by `Settings` and must be provided through local environment or an env file before the FastAPI container can start successfully.

## Development Utilities

| File | Purpose |
|---|---|
| `backend/Dockerfile` | Builds the default FastAPI runtime image from slim requirements |
| `backend/.dockerignore` | Prevents local `.venv`, caches, `.env`, and Airflow logs from entering the image |
| `backend/requirements.txt` | Slim runtime dependency list for default backend |
| `docker-compose.yml` | Starts local Postgres, Qdrant, MinIO, Redis, FastAPI, and optional batch profile |
| `scripts/init_minio.sh` | Creates local MinIO buckets |
| `backend/alembic.ini`, `backend/alembic/` | Reversible production schema migration and autogenerate metadata integration |
| `backend/create_tables.py` | Legacy/development helper for creating missing tables directly from metadata |
| `backend/reset_dev_db.py` | Destructively deletes Qdrant collections and rebuilds DB tables |
| `backend/seed_control_plane.py` | Idempotently creates one complete namespaced control-plane graph |
| `backend/validate_control_plane.py` | Introspects the migrated database and reports the Task 22 structural checklist |
| `backend/check_data.py` | Helper for inspecting indexed Qdrant data |
| `backend/cleanup.py` | Helper for deleting document chunks from Qdrant |
| `test_chunkers.sh` | End-to-end smoke test using `Rapport_de_stage_bac+3.pdf` |
| `backend/tests/test_chunker_registry.py` | Registry metadata and lightweight import tests |
| `backend/tests/test_chunkers_api.py` | `/chunkers` and invalid chunker API tests when FastAPI is installed |
| `backend/tests/test_control_plane_models.py` | Tasks 4–11 table, foreign-key, status, uniqueness, and composite-index tests |
| `backend/tests/test_control_plane_database.py` | Tasks 21–22 isolated PostgreSQL seed, constraint, relationship, lifecycle, schema, and migration tests |
| `backend/tests/test_realtime_streaming.py` | Task 23 SSE, replay, fallback, ownership, token, disconnect, heartbeat, and optional live Redis tests |
| `backend/tests/test_pipeline_artifacts.py` | Task 25 deterministic Silver/Gold Parquet, retry, empty input, and embedding mismatch tests |
| `backend/tests/evaluate.py` | Evaluation helper for local experiments |

## Current Design Notes

- Alembic is the production schema path. Revision `20260711_0001` upgrades an empty database to the full schema and downgrades cleanly; `create_tables.py` remains a development compatibility helper.
- Qdrant is the vector store; Postgres stores control-plane ownership, version/run lineage, chunk metadata, and query/retrieval audit metadata.
- FastEmbed handles both default dense embeddings and BM25 sparse vectors.
- R2/S3 storage is used only for optional multimodal PDF page images.
- The text ingestion endpoint rejects the `multimodal` chunker because multimodal has its own endpoint.
- The registry is built for SaaS frontend display and does not expose callable paths publicly.
- The default Docker image is intentionally text-RAG focused; optional multimodal and CrossEncoder rerank dependencies should be isolated.
- The repository currently has no frontend; the API is ready for a frontend to consume `/chunkers` and the CRUD/RAG endpoints.
