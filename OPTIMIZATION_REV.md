# Optimization Revision - Fix Summary
Date: 2026-07-08

This file documents the fixes applied after the first optimization review.
The goal was to remove the highest-risk development and technical problems
without rewriting the whole backend.

## 1. Safer Configuration
- `backend/app/core/config.py` no longer requires Gemini, Groq, or R2 keys at startup.
- Provider keys are checked only when that provider is used.
- R2 settings are checked only for multimodal PDF ingestion.
- Added `DEBUG_RETURN_CONTEXT`, `MAX_UPLOAD_BYTES`, and `MAX_MULTIMODAL_PAGES`.
- Added `.env.example` and updated the README environment section.
Concept: optional features should not break normal app boot.

## 2. Tenant-Safe Qdrant Collections
- `backend/app/api/projects.py` now creates collections from project UUIDs.
- Display names are no longer used as collection names.
- Same-name projects can no longer share or delete each other's vectors.
- Project deletion also attempts to delete the related multimodal collection.
Concept: user labels should not become infrastructure identifiers.

## 3. Non-Destructive Database Setup
- `backend/create_tables.py` now only creates missing tables.
- Destructive reset behavior moved to `backend/reset_dev_db.py`.
- README now separates normal setup from local reset.
Concept: setup commands must be safe by default.

## 4. Lazy Loading
- `embedder.py` lazy-loads the BGE model.
- Semantic and late chunkers reuse the shared embedder.
- Sparse BM25 and reranker models are lazy-loaded.
- `storage.py` lazy-loads the R2 client.
Concept: importing routes should be cheap; heavy services should load on demand.

## 5. Async Route Protection
- Ingestion parsing, chunking, embedding, and indexing now run in worker threads.
- Query embedding, retrieval, Qdrant search, and LLM calls are also offloaded.
- Delete cleanup operations are offloaded too.
Concept: async endpoints should avoid blocking the event loop.

## 6. Ingestion Reliability
- Uploads enforce `MAX_UPLOAD_BYTES`.
- Empty extracted documents now return a clear error.
- File validation checks extension and MIME type.
- Failed DB saves trigger best-effort Qdrant cleanup.
- Failed multimodal ingestion triggers best-effort Qdrant and R2 cleanup.
- Sample chunks are hidden unless debug output is enabled.
Concept: cross-system writes need cleanup because Postgres, Qdrant, and R2 are not one transaction.

## 7. Query Safety
- `/rag/query` validates that `document_id` belongs to the requested project.
- Retrieved chunks are hidden by default.
- Clients can request chunks with `include_context=true`.
- Missing provider keys now produce clear service errors.
Concept: retrieved context can contain sensitive document data, so it should be opt-in.

## 8. Cleanup, Validation, and Tokenizing
- Multimodal page limits are checked before rendering all pages.
- Deleting multimodal documents/projects now attempts R2 image cleanup.
- Registration normalizes emails and requires stronger passwords.
- Updating your email to the same value no longer conflicts with your own account.
- Project names are trimmed and validated.
- Added indexes for project/document ownership lookups.
- Sentence chunkers now fall back if NLTK tokenizer data is missing.
Concept: validate boundaries, index ownership checks, and avoid hidden runtime data requirements.

## Verification
- Passed: `python3 -m compileall -q backend/app backend/create_tables.py backend/reset_dev_db.py`
- Not run: full API smoke tests because backend dependencies are not installed here (`fastapi` missing).
