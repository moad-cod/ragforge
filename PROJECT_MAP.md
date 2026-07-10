# RAGForge Project Map

RAGForge is a FastAPI SaaS backend for authenticated, multi-tenant Retrieval-Augmented Generation. It ingests files and web sources, versions document content, chunks and embeds text, stores dense and sparse vectors in Qdrant, and answers questions through OpenAI-compatible LLM providers.

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
| Models | `backend/app/models/*.py` | One SQLAlchemy model per table; `tables.py` remains a compatibility export |
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
    models/
      __init__.py
      organization.py
      user.py
      project.py
      document.py
      document_version.py
      tables.py
    services/
      chunkers/
      retrieval/
      embedder.py
      indexer.py
      parser.py
      retriever.py
      storage.py
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
```

Projects use UUID-based Qdrant collection names (`project_<uuid>`) so display names can be changed without reindexing and cannot collide across tenants. `Document` is the logical user-facing asset; `DocumentVersion` records immutable ingestion attempts/content versions for that asset.

## Model Package Layout

The model package now follows one table per file:

| Table | Model file |
|---|---|
| `organizations` | `backend/app/models/organization.py` |
| `users` | `backend/app/models/user.py` |
| `projects` | `backend/app/models/project.py` |
| `documents` | `backend/app/models/document.py` |
| `document_versions` | `backend/app/models/document_version.py` |

`backend/app/models/tables.py` imports and re-exports all models to keep existing imports working:

```python
from app.models.tables import Organization, User, Project, Document, DocumentVersion
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
| Ingest | `POST /ingest/file`, `POST /ingest/url`, `POST /ingest/gdrive`, `POST /ingest/multimodal` |
| Query | `POST /rag/query`, `POST /rag/multimodal-query` |

`DocumentVersion` is intentionally exposed through `GET /documents/{document_id}/versions`, not as a separate top-level `/document-versions` router. That keeps versions scoped under their parent document and enforces document ownership before listing version metadata.

## Docker And Local Services

Default `docker compose up -d --build` services:

| Service | Role |
|---|---|
| `postgres` | Main application PostgreSQL database |
| `qdrant` | Vector database for dense, sparse, and optional multivector search |
| `minio` | Local S3-compatible object storage |
| `minio-init` | Creates local buckets through `scripts/init_minio.sh` |
| `redis` | Local Redis service reserved for async/batch workflows |
| `fastapi` | Backend app built from `backend/Dockerfile` |

The FastAPI container uses `/app` as its working directory, mounts `./backend:/app` for development reloads, installs `backend/requirements.txt`, and starts with:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Batch profile services, enabled with `--profile batch`, add Airflow metadata/webserver/scheduler services and Spark for batch experiments.

## Requirements Strategy

`backend/requirements.txt` is intentionally a slim default runtime set. It includes FastAPI, SQLAlchemy/asyncpg, Qdrant, FastEmbed, document parsers, auth, OpenAI/Groq clients, and S3/R2 support.

It intentionally does not include older full frozen-environment dependencies or heavy optional stacks such as PyTorch/CUDA wheels, `sentence-transformers`, `transformers`, `colpali_engine`, LangChain, and evaluation/training packages.

Optional multimodal ColPali and CrossEncoder reranking should be added through a separate image, profile, or extras file if they are needed.

## Ingestion Flow

1. The user authenticates with JWT.
2. The API verifies project ownership.
3. The API gets or creates a logical `Document`.
4. The source content is hashed to prevent duplicate versions for the same document.
5. The source is parsed into text or, for optional multimodal ingestion, rendered page images.
6. The chunker ID is validated through the central registry.
7. Text chunkers produce chunks.
8. FastEmbed creates normalized dense BGE vectors.
9. FastEmbed BM25 creates sparse vectors.
10. Qdrant stores vectors with `project_id` and `document_id` payload filters.
11. PostgreSQL stores or updates `Document` and creates a `DocumentVersion`.
12. On failure, ingestion attempts best-effort cleanup of Qdrant/R2 artifacts.

Heavy parsing, embedding, indexing, retrieval, and LLM calls are offloaded with `asyncio.to_thread` to avoid blocking FastAPI's event loop.

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
  -> FastEmbed BGE query embedding
  -> Qdrant hybrid dense+sparse search
  -> optional rerank
  -> context prompt
  -> Gemini or Groq OpenAI-compatible chat completion
  -> answer
```

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
- `MAX_UPLOAD_BYTES`
- `MAX_MULTIMODAL_PAGES`
- `DEBUG_RETURN_CONTEXT`

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
| `backend/create_tables.py` | Creates missing database tables |
| `backend/reset_dev_db.py` | Destructively deletes Qdrant collections and rebuilds DB tables |
| `backend/check_data.py` | Helper for inspecting indexed Qdrant data |
| `backend/cleanup.py` | Helper for deleting document chunks from Qdrant |
| `test_chunkers.sh` | End-to-end smoke test using `Rapport_de_stage_bac+3.pdf` |
| `backend/tests/test_chunker_registry.py` | Registry metadata and lightweight import tests |
| `backend/tests/test_chunkers_api.py` | `/chunkers` and invalid chunker API tests when FastAPI is installed |
| `backend/tests/evaluate.py` | Evaluation helper for local experiments |

## Current Design Notes

- The project uses SQLAlchemy model creation scripts rather than Alembic migrations.
- Qdrant is the vector store; Postgres stores control-plane ownership, document metadata, and document version metadata.
- FastEmbed handles both default dense embeddings and BM25 sparse vectors.
- R2/S3 storage is used only for optional multimodal PDF page images.
- The text ingestion endpoint rejects the `multimodal` chunker because multimodal has its own endpoint.
- The registry is built for SaaS frontend display and does not expose callable paths publicly.
- The default Docker image is intentionally text-RAG focused; optional multimodal and CrossEncoder rerank dependencies should be isolated.
- The repository currently has no frontend; the API is ready for a frontend to consume `/chunkers` and the CRUD/RAG endpoints.
