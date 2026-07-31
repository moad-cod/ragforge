# RAGForge Optimization and Feature Review
Date: 2026-07-08

This file summarizes the current optimized RAGForge backend after the recent architecture, registry, reset, smoke-test, and documentation updates.

## Current Codebase Features

- FastAPI SaaS backend for authenticated multi-tenant RAG.
- JWT auth with register, login, profile update, and account deletion.
- PostgreSQL stores users, projects, and document metadata through SQLAlchemy async.
- Qdrant stores vector data with `project_id` and `document_id` payload filters.
- Project Qdrant collections use UUID-based names to prevent tenant collisions.
- File ingestion supports PDF, DOCX, XLSX, PPTX, CSV, HTML, Markdown, and TXT.
- URL ingestion and Google Drive ingestion are available.
- Multimodal PDF ingestion renders pages, embeds them, stores page images in R2, and indexes multivectors in Qdrant.
- Text RAG queries support Gemini and Groq through OpenAI-compatible clients.
- Multimodal queries retrieve visual PDF pages and send page images to Gemini.

## Chunking System

- `backend/app/services/chunkers/registry.py` is now the single source of truth.
- `GET /chunkers` exposes SaaS-style chunker metadata for frontend product cards.
- Public chunkers are `fixed_size`, `paragraph`, `sentence`, `semantic`, `hierarchical`, `late_chunking`, `proposition`, and `multimodal`.
- `paragraph` remains the default text chunker.
- `multimodal` is exposed in metadata but rejected by `/ingest/file`; it uses `/ingest/multimodal`.
- Registry responses do not expose internal callable paths.
- Internal files such as `registry.py`, `tokenize.py`, `__init__.py`, and `__pycache__` are not treated as chunkers.
- Heavy chunker modules are lazy-loaded through callable paths.

## Retrieval and Indexing

- Text chunks are embedded with lazy-loaded `BAAI/bge-small-en-v1.5`.
- Qdrant text collections use dense vectors and sparse BM25 vectors.
- Hybrid retrieval combines dense and sparse search with RRF.
- A lazy-loaded cross-encoder reranker improves final context selection.
- Hierarchical retrieval can return parent context from child hits.
- Retrieved chunks are hidden by default and can be returned with `include_context=true`.

## Reliability Improvements

- Optional LLM and R2 settings no longer break app startup.
- Provider keys are checked only when the matching provider or feature is used.
- Upload size is capped with `MAX_UPLOAD_BYTES`.
- Multimodal page count is capped with `MAX_MULTIMODAL_PAGES`.
- Empty extracted documents return a clean error.
- Ingestion attempts best-effort cleanup of Qdrant and R2 artifacts after failures.
- Deleting documents/projects attempts related vector and multimodal image cleanup.
- Proposition chunking detects Groq rate/quota, auth, service, and non-JSON failures and falls back cleanly.

## Performance Improvements

- Model clients and ML models are lazy-loaded instead of created at import time.
- R2 client creation is lazy.
- Ingestion parsing, chunking, embedding, and indexing are offloaded with `asyncio.to_thread`.
- Query embedding, retrieval, Qdrant search, LLM calls, and delete cleanup are also offloaded.
- Registry import is lightweight and safe for frontend metadata routes.

## Developer Workflow

- `backend/scripts/create_tables.py` creates missing tables without dropping data.
- `backend/scripts/reset_dev_db.py` destructively deletes all Qdrant collections and rebuilds all database tables for fresh testing.
- `test_chunkers.sh` runs an end-to-end smoke test using `Rapport_de_stage_bac+3.pdf`.
- The smoke test validates `/chunkers`, metadata completeness, invalid chunkers, all text chunkers, document APIs, query APIs, and cleanup.
- `PROJECT_MAP.md` documents architecture, flows, modules, API surface, and design notes.
- `README.md` now matches the current codebase and registry-based chunker system.

## Tests and Verification

- Registry tests validate all 8 public chunkers and ensure heavy modules are not loaded by registry import.
- API tests validate `/chunkers` serialization and invalid chunker handling when FastAPI is installed.
- Recent verification commands:

```bash
PYTHONPATH=/home/snow/Documents/Projects/RAGForge/backend python3 -m unittest backend.tests.test_chunker_registry backend.tests.test_chunkers_api -v
python3 -m compileall -q backend/app backend/tests backend/scripts/create_tables.py backend/scripts/reset_dev_db.py
bash -n test_chunkers.sh
```

## Remaining Optimization Opportunities

- Replace table creation scripts with Alembic migrations before production use.
- Split the large `requirements.txt` into API, ML, multimodal, and dev dependency profiles.
- Add structured logging and request IDs across ingestion and query flows.
- Move long-running ingestion to a real background worker queue.
- Add full integration tests against live Postgres and Qdrant.
- Add rate-limit/backoff handling for Qdrant, Gemini, Groq, and R2 calls.
- Add billing/plan enforcement around premium chunkers such as proposition and multimodal.
