# RAGForge Project Map

RAGForge is a FastAPI SaaS backend for authenticated, multi-tenant Retrieval-Augmented Generation. It ingests documents, chunks and embeds text, stores vectors in Qdrant, and answers questions through OpenAI-compatible LLM providers.

## Architecture

```text
Client
  -> FastAPI routers
  -> Auth / Projects / Documents / Chunkers / Ingest / Query
  -> SQLAlchemy async + PostgreSQL for users, projects, documents
  -> Parser + chunker registry + embedding services
  -> Qdrant dense+sparse vector collections
  -> Hybrid retrieval + reranking
  -> Gemini or Groq chat completion
```

## Main Runtime Modules

| Area | Files | Responsibility |
|---|---|---|
| App entry | `backend/app/main.py` | Creates FastAPI app and mounts routers |
| Config | `backend/app/core/config.py` | Loads `.env`, optional LLM/R2 settings, limits |
| Auth | `backend/app/core/auth.py`, `backend/app/api/auth.py` | JWT auth, register, login, user profile |
| Database | `backend/app/core/db.py`, `backend/app/models/tables.py` | Async engine and SQLAlchemy models |
| Projects | `backend/app/api/projects.py` | Project CRUD and Qdrant collection lifecycle |
| Documents | `backend/app/api/documents.py` | Document list/get/delete and artifact cleanup |
| Ingestion | `backend/app/api/ingest.py` | File, URL, Google Drive, multimodal ingestion |
| Query | `backend/app/api/query.py` | RAG and multimodal query endpoints |
| Chunker catalog | `backend/app/api/chunkers.py`, `backend/app/services/chunkers/registry.py` | Public chunker metadata and validation |
| Parsing | `backend/app/services/parser.py` | PDF, DOCX, XLSX, PPTX, CSV, HTML, text, URL, Drive parsing |
| Embeddings | `backend/app/services/embedder.py` | Lazy BGE embedding model |
| Indexing | `backend/app/services/indexer.py` | Qdrant collection creation, upsert, delete |
| Retrieval | `backend/app/services/retriever.py`, `backend/app/services/retrieval/*` | Dense/sparse hybrid retrieval and reranking |
| Storage | `backend/app/services/storage.py` | Lazy Cloudflare R2 client for page images |

## Data Model

```text
User
  id, email, hashed_password, created_at
  has many Projects

Project
  id, user_id, name, collection, created_at
  has many Documents

Document
  id, project_id, filename, source, chunks, collection, created_at
```

Projects use UUID-based Qdrant collection names (`project_<uuid>`) so display names cannot collide across tenants.

## Ingestion Flow

1. The user authenticates with JWT.
2. The API verifies project ownership.
3. The source is parsed into text or page images.
4. The chunker ID is validated through the central registry.
5. Text chunkers produce chunks, then BGE creates dense vectors.
6. BM25 sparse vectors are generated for hybrid retrieval.
7. Qdrant stores vectors with `project_id` and `document_id` payload filters.
8. PostgreSQL stores the document metadata.
9. On failure, ingestion attempts best-effort cleanup of Qdrant/R2 artifacts.

Heavy parsing, embedding, indexing, retrieval, and LLM calls are offloaded with `asyncio.to_thread` to avoid blocking FastAPI's event loop.

## Chunking System

The chunker registry is the single source of truth. It exposes product metadata for frontends through `GET /chunkers` and validates ingestion requests.

Public chunkers:

| ID | Product Name | Tier | Status |
|---|---|---|---|
| `fixed_size` | Starter Chunking | base | stable |
| `paragraph` | Base Chunking | base | stable |
| `sentence` | Precision Chunking | pro | stable |
| `semantic` | Semantic Chunking | pro | beta |
| `hierarchical` | Structured Chunking | business | beta |
| `late_chunking` | Late Interaction Chunking | ultimate | beta |
| `proposition` | Ultimate Chunking | ultimate | beta |
| `multimodal` | Multimodal Chunking | ultimate | experimental |

`registry.py`, `tokenize.py`, `__init__.py`, and `__pycache__` are internal and are not public chunkers. The registry uses lazy callable paths so importing metadata does not load heavy ML or multimodal models.

## Retrieval and Generation

Text RAG query flow:

```text
question -> BGE query embedding -> Qdrant hybrid dense+sparse search -> reranker -> context prompt -> Gemini/Groq -> answer
```

Optional query controls:

- `document_id` filters retrieval to one document.
- `use_parent_context` expands hierarchical child hits to parent context.
- `include_context` returns retrieved chunks for debugging/trusted clients.

Multimodal query flow:

```text
question -> ColQwen query vectors -> Qdrant multivector page search -> page image URLs -> Gemini vision response
```

## API Surface

| Area | Endpoint |
|---|---|
| Health | `GET /health` |
| Auth | `POST /auth/register`, `POST /auth/login`, `GET/PATCH/DELETE /auth/me` |
| Projects | `POST/GET /projects/`, `GET/PATCH/DELETE /projects/{project_id}` |
| Documents | `GET /documents/?project_id=...`, `GET/DELETE /documents/{document_id}` |
| Chunkers | `GET /chunkers` |
| Ingest | `POST /ingest/file`, `POST /ingest/url`, `POST /ingest/gdrive`, `POST /ingest/multimodal` |
| Query | `POST /rag/query`, `POST /rag/multimodal-query` |

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
- R2 settings for multimodal page image storage.

## Development Utilities

| File | Purpose |
|---|---|
| `docker-compose.yml` | Starts PostgreSQL and Qdrant |
| `backend/create_tables.py` | Creates missing database tables |
| `backend/reset_dev_db.py` | Destructively deletes Qdrant collections and rebuilds DB tables |
| `test_chunkers.sh` | End-to-end smoke test using `Rapport_de_stage_bac+3.pdf` |
| `backend/tests/test_chunker_registry.py` | Registry metadata and lightweight import tests |
| `backend/tests/test_chunkers_api.py` | `/chunkers` and invalid chunker API tests when FastAPI is installed |

## Current Design Notes

- The project uses SQLAlchemy model creation scripts rather than Alembic migrations.
- Qdrant is the vector store; Postgres stores ownership and document metadata.
- R2 is used only for multimodal PDF page images.
- The text ingestion endpoint rejects the `multimodal` chunker because multimodal has its own endpoint.
- The registry is built for SaaS frontend display and does not expose callable paths publicly.
- The repository currently has no frontend; the API is ready for a frontend to consume `/chunkers`.
