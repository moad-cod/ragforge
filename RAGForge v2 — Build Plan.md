# RAGForge v2 — Data Engineering + Agentic RAG Platform

## Goal

Evolve **RAGForge** from a classic RAG backend into a full **Data Engineering + Agentic RAG platform**.

RAGForge v2 adds:

- Data modeling for document versions, ingestion runs, chunks, embeddings, and query logs
- MinIO object storage with Bronze / Silver / Gold layers
- Spark batch processing in local mode
- Parquet-based lakehouse-style storage
- Airflow orchestration for offline ingestion pipelines
- Redis for query caching, session state, and temporary job progress
- LangGraph for agentic per-query RAG workflows
- Qdrant as the vector search engine
- PostgreSQL as the durable metadata source of truth
- FastAPI as the platform API

This version intentionally avoids **Hadoop** and **Hive**.  
Storage is handled with **MinIO**, using an S3-compatible object storage pattern that is closer to modern production data platforms.

---

## Target Architecture

```text
Upload
  ↓
FastAPI
  ↓
Postgres ingestion_run row: status = landed
  ↓
MinIO Bronze: raw document
  ↓
Airflow triggers ingestion pipeline
  ↓
Spark job: parse, clean, deduplicate, chunk
  ↓
MinIO Silver: cleaned chunks as Parquet
  ↓
Embedding job
  ↓
MinIO Gold: embedded chunk metadata
  ↓
Qdrant: vector index
  ↓
Postgres: documents, versions, chunks, runs, query logs
```

---

## Core Design Principles

```text
PostgreSQL = durable source of truth for metadata and status
MinIO      = durable source of truth for raw and processed data
Qdrant     = rebuildable vector index
Redis      = temporary cache, session, and progress store
Airflow    = offline/batch orchestration
LangGraph  = online/per-query orchestration
FastAPI    = external API layer
```

Important rules:

- Do not process large documents synchronously inside upload requests.
- Every document upload must create a version.
- Re-ingestion must create a new `document_version_id`.
- Qdrant must be rebuildable from Gold data.
- Redis must not be the only source of truth for ingestion status.
- Airflow DAGs should call reusable scripts/jobs, not contain all business logic.
- Keep the old `/rag/query` endpoint stable while adding `/rag/agent-query`.

---

## Updated Data Flow

```text
Documents
  → MinIO Bronze: raw files
  → Spark / Python job: parse, clean, deduplicate, chunk
  → MinIO Silver: cleaned chunks as Parquet
  → Embedding job
  → MinIO Gold: embedded chunk metadata
  → Qdrant: vector points
  → PostgreSQL: metadata, status, versions, chunks
```

---

## Lakehouse Layers

### Bronze Layer

Stores original uploaded files exactly as received.

```text
bronze/
  org_id={org_id}/
    project_id={project_id}/
      document_id={document_id}/
        version={version_number}/
          raw/
            {original_filename}
```

Example:

```text
bronze/org_id=org_123/project_id=proj_456/document_id=doc_789/version=1/raw/report.pdf
```

Bronze contains:

- raw uploaded PDF, DOCX, PPTX, CSV, TXT, HTML, Markdown, etc.
- original filename
- content hash
- upload metadata
- no cleaning or transformation

---

### Silver Layer

Stores cleaned and chunked document data as Parquet.

```text
silver/
  org_id={org_id}/
    project_id={project_id}/
      document_id={document_id}/
        version={version_number}/
          chunks.parquet
          stats.json
```

Silver Parquet schema:

```text
project_id string
document_id string
document_version_id string
chunk_id string
chunk_index int
chunker_id string
text string
content_hash string
token_count int
page_start int
page_end int
language string
metadata_json string
created_at timestamp
```

Silver quality checks:

- `document_id` must not be null
- `document_version_id` must not be null
- `text` must not be empty
- duplicate chunks should be removed by `content_hash`
- `chunk_count` must be greater than zero
- language detection should be stored when possible

---

### Gold Layer

Stores enriched chunk metadata after embedding.

```text
gold/
  org_id={org_id}/
    project_id={project_id}/
      document_id={document_id}/
        version={version_number}/
          embedded_chunks.parquet
          embedding_stats.json
```

Gold Parquet schema:

```text
chunk_id string
project_id string
document_id string
document_version_id string
chunk_index int
text string
content_hash string
embedding_model string
embedding_dim int
qdrant_collection string
qdrant_point_id string
metadata_json string
embedded_at timestamp
```

Gold is used to:

- rebuild Qdrant indexes
- audit embedding runs
- debug retrieval quality
- compare embedding models
- support future evaluation pipelines

---

## PostgreSQL Data Model

### `documents`

Logical document record.

```text
id UUID primary key
project_id UUID not null
current_version_id UUID nullable
source_type text
filename text
mime_type text
extension text
status text
created_by UUID
created_at timestamp
updated_at timestamp
deleted_at timestamp nullable
```

Recommended statuses:

```text
uploaded
landed
processing
chunked
embedded
indexed
failed
deleted
```

---

### `document_versions`

Tracks every upload or re-ingestion of a document.

```text
id UUID primary key
document_id UUID not null
version_number int not null
content_hash text not null
bronze_path text
silver_path text
gold_path text
parser_name text
chunker_id text
embedding_model text
status text
error_message text nullable
created_at timestamp
```

Purpose:

- prevent silent overwrites
- support re-ingestion history
- compare chunking strategies
- rebuild Qdrant from a known version
- support evaluation by document version

---

### `ingestion_runs`

Tracks each ingestion pipeline execution.

```text
id UUID primary key
project_id UUID not null
document_id UUID not null
document_version_id UUID not null
status text
started_at timestamp nullable
finished_at timestamp nullable
error_message text nullable
airflow_dag_run_id text nullable
created_by UUID
created_at timestamp
```

Recommended statuses:

```text
landed
queued
running
silver_completed
gold_completed
indexed
failed
cancelled
```

---

### `chunks`

Stores chunk metadata in PostgreSQL.

```text
id UUID primary key
project_id UUID not null
document_id UUID not null
document_version_id UUID not null
ingestion_run_id UUID nullable
qdrant_point_id text unique
chunk_index int not null
text text not null
content_hash text not null
token_count int nullable
page_start int nullable
page_end int nullable
section_title text nullable
metadata_json jsonb
created_at timestamp
```

Postgres stores chunk metadata.  
Qdrant stores vectors.  
MinIO Silver/Gold stores Parquet data.

---

### `embedding_runs`

Tracks embedding generation.

```text
id UUID primary key
project_id UUID not null
document_version_id UUID not null
embedding_model text not null
status text
total_chunks int default 0
embedded_chunks int default 0
started_at timestamp nullable
finished_at timestamp nullable
error_message text nullable
created_at timestamp
```

---

### `query_logs`

Tracks user queries.

```text
id UUID primary key
project_id UUID not null
user_id UUID not null
question text not null
normalized_question_hash text
provider text
model text
latency_ms int nullable
cache_hit boolean default false
created_at timestamp
```

---

### `retrieval_logs`

Tracks retrieved chunks for debugging and evaluation.

```text
id UUID primary key
query_log_id UUID not null
chunk_id UUID nullable
qdrant_score float nullable
rerank_score float nullable
rank int
retrieval_strategy text
used_in_answer boolean default false
created_at timestamp
```

---

## Qdrant Data Model

Each chunk becomes one Qdrant point.

Recommended point ID:

```text
{document_version_id}:{chunk_index}
```

Qdrant payload:

```json
{
  "organization_id": "org_uuid",
  "project_id": "project_uuid",
  "document_id": "document_uuid",
  "document_version_id": "version_uuid",
  "chunk_id": "chunk_uuid",
  "chunk_index": 12,
  "title": "Document title",
  "source_type": "file_upload",
  "page_start": 4,
  "page_end": 5,
  "section_title": "Architecture",
  "text": "Chunk text..."
}
```

Every query must filter by `project_id`.

Optional filters:

- `document_id`
- `document_version_id`
- `source_type`
- `page_start`
- metadata fields

---

## Redis Usage

Redis is used only for fast temporary state.

Use Redis for:

```text
query cache
temporary ingestion progress
conversation/session cache
rate-limit counters
```

Do not use Redis as the only durable source for:

```text
document status
ingestion history
query history
chunk metadata
embedding records
```

Recommended keys:

```text
rag:answer:{project_id}:{model}:{retrieval_config_hash}:{question_hash}
ingestion_job:{ingestion_run_id}:status
session:{user_id}:{conversation_id}
rate_limit:{user_id}
```

Recommended TTLs:

```text
query cache: 1h to 24h
job status cache: 24h
session cache: 1h to 7d
rate limit counters: short TTL
```

---

## Airflow DAGs

### DAG 1 — Ingestion Pipeline

Name:

```text
ragforge_ingestion_pipeline
```

Flow:

```text
validate_bronze
  ↓
bronze_to_silver_spark
  ↓
silver_to_gold_embed
  ↓
upsert_qdrant
  ↓
update_postgres_status
```

Each Airflow task should call a reusable script:

```bash
python jobs/bronze_to_silver.py --ingestion-run-id ...
python jobs/silver_to_gold.py --ingestion-run-id ...
python jobs/upsert_qdrant.py --ingestion-run-id ...
python jobs/update_status.py --ingestion-run-id ...
```

Airflow should orchestrate.  
Business logic should stay inside testable Python jobs.

---

### DAG 2 — Corpus Maintenance

Name:

```text
ragforge_corpus_maintenance
```

Responsibilities:

- detect failed ingestion runs
- detect stuck processing jobs
- detect missing MinIO objects
- detect stale document versions
- detect Qdrant collection inconsistencies
- optionally rebuild Qdrant from Gold
- run row-count checks between Silver, Gold, Qdrant, and Postgres

Schedule:

```text
daily or weekly
```

---

## LangGraph Agentic RAG

The old `/rag/query` endpoint should remain as the stable linear pipeline.

Add a new endpoint:

```text
POST /rag/agent-query
```

This endpoint uses LangGraph.

### Agent Graph

```text
Start
  ↓
Normalize Query
  ↓
Cache Check
  ↓
Query Router
  ├── Direct Answer
  ├── Clarify
  └── Retrieve
          ↓
      Grade Relevance
          ├── Weak → Rewrite Query → Retrieve
          └── Good → Generate Answer
                          ↓
                    Grade Groundedness
                          ├── Failed → Retry / Retrieve
                          └── Passed → Save + Cache + Return
```

### Graph State

```python
from typing import TypedDict

class RAGState(TypedDict):
    project_id: str
    user_id: str
    question: str
    normalized_question: str
    retrieved_chunks: list[dict]
    answer: str | None
    route: str | None
    relevance_score: float | None
    groundedness_score: float | None
    retry_count: int
    cache_hit: bool
```

### Nodes

```text
Normalize Query
Cache Check
Query Router
Retrieve
Grade Relevance
Rewrite Query
Generate Answer
Grade Groundedness
Save Query Log
Cache Answer
Return Response
```

Important:

```text
max_retries = 2
```

Agentic loops must always have retry limits.

---

## Updated API Behavior

### File Upload

Old behavior:

```text
upload → parse → chunk → embed → index inside request
```

New behavior:

```text
upload → save raw file to Bronze → create ingestion run → return immediately
```

Endpoint:

```text
POST /ingest/file
```

Response:

```json
{
  "document_id": "uuid",
  "document_version_id": "uuid",
  "ingestion_run_id": "uuid",
  "status": "landed"
}
```

---

### Ingestion Status

New endpoint:

```text
GET /ingest/runs/{ingestion_run_id}
```

Response:

```json
{
  "ingestion_run_id": "uuid",
  "document_id": "uuid",
  "document_version_id": "uuid",
  "status": "indexed",
  "progress": {
    "bronze": true,
    "silver": true,
    "gold": true,
    "qdrant": true
  }
}
```

---

### Agentic Query

New endpoint:

```text
POST /rag/agent-query
```

Request:

```json
{
  "question": "What is the document about?",
  "project_id": "uuid",
  "provider": "gemini",
  "model": null,
  "document_id": null,
  "use_cache": true
}
```

Response:

```json
{
  "question": "What is the document about?",
  "answer": "...",
  "project_id": "uuid",
  "provider": "gemini",
  "model": "gemini-2.5-flash",
  "cache_hit": false,
  "route": "retrieve",
  "relevance_score": 0.83,
  "groundedness_score": 0.91,
  "retrieved_chunks": []
}
```

---

## Updated Folder Structure

```text
backend/
  app/
    api/
      auth.py
      projects.py
      documents.py
      ingest.py
      query.py
      agent_query.py
      chunkers.py

    core/
      auth.py
      config.py
      db.py
      redis.py
      storage.py

    models/
      tables.py

    services/
      chunkers/
        fixed_size.py
        paragraph.py
        sentence.py
        semantic.py
        hierarchical.py
        late_chunking.py
        proposition.py
        multimodal.py
        registry.py
        tokenize.py

      storage/
        minio_client.py
        paths.py

      retrieval/
        dense.py
        sparse.py
        rerank.py
        hybrid.py

      agents/
        graph.py
        state.py
        nodes.py
        tools.py

      parser.py
      embedder.py
      indexer.py
      retriever.py

  jobs/
    bronze_to_silver.py
    silver_to_gold.py
    upsert_qdrant.py
    rebuild_index.py
    update_status.py

  dags/
    ingestion_pipeline.py
    corpus_maintenance.py

  scripts/
    create_minio_buckets.py
    test_minio.py
    seed_sample_docs.py
    wait_for_ingestion.py
    e2e_v2.sh

  alembic/
    versions/

  requirements.txt
```

---

## Docker Compose Services

Final local platform services:

```text
fastapi
postgres
qdrant
minio
redis
airflow-webserver
airflow-scheduler
spark
```

Ports:

```text
FastAPI: 8000
Postgres: 5432
Qdrant: 6333
MinIO API: 9000
MinIO Console: 9001
Redis: 6379
Airflow: 8080
```

---

## Makefile Commands

```makefile
up:
	docker compose up -d

down:
	docker compose down

api:
	cd backend && uvicorn app.main:app --reload

migrate:
	cd backend && alembic upgrade head

test-minio:
	cd backend && python scripts/test_minio.py

create-buckets:
	cd backend && python scripts/create_minio_buckets.py

spark-bronze-silver:
	cd backend && python jobs/bronze_to_silver.py

spark-silver-gold:
	cd backend && python jobs/silver_to_gold.py

airflow-dag-test:
	cd backend && airflow dags test ragforge_ingestion_pipeline

e2e-v2:
	cd backend && bash scripts/e2e_v2.sh
```

---

# 14-Day Implementation Plan

## Week 1 — Data Foundation

### Day 1 — Data Modeling

- [ ] Audit current PostgreSQL schema
- [ ] Design new tables:
  - `documents`
  - `document_versions`
  - `ingestion_runs`
  - `chunks`
  - `embedding_runs`
  - `query_logs`
  - `retrieval_logs`
- [ ] Add `document_version_id` for re-ingestion history
- [ ] Add `bronze_path`, `silver_path`, `gold_path`
- [ ] Add durable status fields
- [ ] Create Alembic migration
- [ ] Apply migration locally
- [ ] Verify with sample inserts

Deliverable:

```text
Alembic migration + verified local schema
```

---

### Day 2 — MinIO Setup

- [ ] Add MinIO service to `docker-compose.yml`
- [ ] Add MinIO console on port `9001`
- [ ] Add environment variables:
  - `MINIO_ENDPOINT`
  - `MINIO_ACCESS_KEY`
  - `MINIO_SECRET_KEY`
  - `MINIO_BUCKET_BRONZE`
  - `MINIO_BUCKET_SILVER`
  - `MINIO_BUCKET_GOLD`
- [ ] Create buckets:
  - `bronze`
  - `silver`
  - `gold`
- [ ] Write `scripts/create_minio_buckets.py`
- [ ] Write `scripts/test_minio.py`
- [ ] Document bucket paths in README

Deliverable:

```text
MinIO running locally + bucket creation script + upload/download test
```

---

### Day 3 — Bronze Layer Raw Ingestion

- [ ] Update `/ingest/file`
- [ ] Compute file hash
- [ ] Check duplicate uploads by hash
- [ ] Create `documents` row
- [ ] Create `document_versions` row
- [ ] Upload raw file to MinIO Bronze
- [ ] Create `ingestion_runs` row with status `landed`
- [ ] Return `ingestion_run_id`
- [ ] Add status endpoint for ingestion runs
- [ ] Test with 20–30 sample documents

Deliverable:

```text
Upload endpoint lands raw files in Bronze and returns ingestion_run_id
```

---

### Day 4–5 — Spark Bronze to Silver

- [ ] Set up Spark local mode
- [ ] Write `jobs/bronze_to_silver.py`
- [ ] Read ingestion run metadata from PostgreSQL
- [ ] Download/read Bronze document from MinIO
- [ ] Parse document using existing parser logic
- [ ] Clean extracted text
- [ ] Deduplicate by content hash
- [ ] Chunk using selected chunker
- [ ] Write chunks to Silver Parquet
- [ ] Write `stats.json`
- [ ] Update ingestion run status to `silver_completed`
- [ ] Add data-quality checks:
  - no empty text
  - no null document IDs
  - chunk count > 0
  - duplicate rate measured
  - language detection stored when possible

Deliverable:

```text
Silver Parquet output + stats.json for sample documents
```

---

### Day 6 — Silver to Gold Embedding

- [ ] Write `jobs/silver_to_gold.py`
- [ ] Read Silver Parquet chunks
- [ ] Generate embeddings with existing embedding model
- [ ] Write Gold Parquet metadata
- [ ] Create/update chunk rows in PostgreSQL
- [ ] Upsert vectors into Qdrant
- [ ] Update `embedding_runs`
- [ ] Update document version status to `indexed`
- [ ] Verify Qdrant search works after indexing

Deliverable:

```text
Gold Parquet + Qdrant vectors + Postgres chunk metadata
```

---

### Day 7 — Buffer and Review

- [ ] Fix bugs from Days 1–6
- [ ] Verify Bronze/Silver/Gold paths exist
- [ ] Verify Qdrant can be rebuilt from Gold
- [ ] Verify document delete removes Qdrant points
- [ ] Write architecture diagram
- [ ] Commit progress
- [ ] Tag release:

```bash
git tag v2-week1
```

Deliverable:

```text
Working local lakehouse-style ingestion pipeline
```

---

## Week 2 — Orchestration, Cache, Agentic RAG

### Day 8 — Airflow Setup

- [ ] Add Airflow webserver and scheduler to `docker-compose.yml`
- [ ] Use LocalExecutor
- [ ] Use PostgreSQL or SQLite metadata DB
- [ ] Write DAG `ragforge_ingestion_pipeline`
- [ ] Tasks:
  - `validate_bronze`
  - `bronze_to_silver_spark`
  - `silver_to_gold_embed`
  - `upsert_qdrant`
  - `update_postgres_status`
- [ ] Test DAG manually with sample documents

Deliverable:

```text
Airflow DAG runs ingestion pipeline end-to-end
```

---

### Day 9 — Airflow Maintenance DAG

- [ ] Write DAG `ragforge_corpus_maintenance`
- [ ] Add stale-document detection
- [ ] Add stuck-job detection
- [ ] Add failed-ingestion detection
- [ ] Add missing-MinIO-object check
- [ ] Add row-count checks:
  - Bronze documents
  - Silver chunks
  - Gold embedded chunks
  - PostgreSQL chunks
  - Qdrant points
- [ ] Add optional Qdrant rebuild from Gold
- [ ] Schedule maintenance DAG

Deliverable:

```text
Maintenance DAG with basic data quality and recovery checks
```

---

### Day 10 — Redis Integration

- [ ] Add Redis service to `docker-compose.yml`
- [ ] Add Redis client in FastAPI
- [ ] Implement query cache
- [ ] Implement ingestion progress cache
- [ ] Add cache key normalization
- [ ] Add TTL configuration
- [ ] Add cache hit/miss response field
- [ ] Optional: add conversation/session state in Redis
- [ ] Test repeated query returns `cache_hit = true`

Deliverable:

```text
Redis query cache + temporary ingestion progress tracking
```

---

### Day 11–12 — LangGraph Agentic RAG

- [ ] Add `/rag/agent-query`
- [ ] Define graph state
- [ ] Implement nodes:
  - Normalize Query
  - Cache Check
  - Query Router
  - Retrieve
  - Grade Relevance
  - Rewrite Query
  - Generate Answer
  - Grade Groundedness
  - Save Query Log
  - Cache Answer
- [ ] Add retry cap
- [ ] Wrap existing retrieval pipeline as a LangGraph tool
- [ ] Store query logs and retrieval logs
- [ ] Keep `/rag/query` unchanged for stable fallback

Deliverable:

```text
Agentic RAG endpoint with routing, retrieval grading, answer grading, and cache support
```

---

### Day 13 — Integration Pass

- [ ] Full end-to-end test:
  - upload document
  - land in Bronze
  - trigger Airflow DAG
  - generate Silver
  - generate Gold
  - upsert Qdrant
  - query via LangGraph
  - repeat query and verify cache hit
- [ ] Fix MinIO path bugs
- [ ] Fix Qdrant upsert bugs
- [ ] Fix Redis key bugs
- [ ] Add logging/tracing across ingestion and query paths
- [ ] Create command:

```bash
make e2e-v2
```

Deliverable:

```text
One-command end-to-end v2 platform test
```

---

### Day 14 — Docs, Demo, Polish

- [ ] Update README
- [ ] Add architecture diagram
- [ ] Add setup instructions
- [ ] Add Stack Summary
- [ ] Add “What changed from v1 to v2”
- [ ] Record short demo:
  - upload
  - Airflow run
  - query
  - cached repeat query
- [ ] Add CV/portfolio bullet
- [ ] Push final commit
- [ ] Tag release:

```bash
git tag v2-release
```

Deliverable:

```text
Documented v2 release ready for portfolio/demo
```

---

## Stack Summary

| Layer | Tool | Role |
|---|---|---|
| API | FastAPI | Upload, query, auth, project management |
| Metadata DB | PostgreSQL | Source of truth for users, projects, documents, chunks, runs |
| Object Storage | MinIO | Bronze/Silver/Gold lake storage |
| Batch Processing | Spark local mode | Cleaning, deduplication, chunking, stats |
| File Format | Parquet | Silver/Gold analytical storage |
| Batch Orchestration | Airflow | Ingestion and maintenance DAGs |
| Online Orchestration | LangGraph | Agentic RAG query loop |
| Cache | Redis | Query cache, session state, temporary job progress |
| Vector DB | Qdrant | Dense vector retrieval |
| LLMs | Gemini / Groq | Answer generation and grading |
| Containers | Docker Compose | Local platform environment |

---

## Dropped Components

The following are intentionally not used:

| Component | Reason |
|---|---|
| Hadoop | Too heavy for this project; replaced by MinIO object storage |
| Hive | Not needed for local lakehouse-style pipeline |
| YARN | Spark runs in local mode |
| HDFS | Replaced by MinIO |
| Celery | Not required for this phase; Airflow handles batch orchestration |

---

## What Changed from RAGForge v1 to v2

RAGForge v1 was a classic RAG backend:

```text
upload → parse → chunk → embed → Qdrant → query
```

RAGForge v2 becomes a data engineering and agentic RAG platform:

```text
upload
  → Bronze raw storage
  → Silver cleaned chunks
  → Gold embedded metadata
  → Qdrant vector index
  → LangGraph agentic query loop
  → Redis cache
  → query/retrieval logs
```

Main improvements:

- raw files are preserved in Bronze
- processed chunks are stored in Silver Parquet
- embedding metadata is stored in Gold
- ingestion is tracked with durable runs
- document versions prevent silent overwrites
- Qdrant can be rebuilt from Gold
- Airflow orchestrates offline pipelines
- Redis improves online performance
- LangGraph improves query reasoning and grounding
- query and retrieval logs support evaluation

---

## Portfolio / CV Bullet

```text
Built RAGForge v2, a Data Engineering + Agentic RAG platform using FastAPI, PostgreSQL, Qdrant, MinIO, Spark, Airflow, Redis, and LangGraph. Designed a lakehouse-style Bronze/Silver/Gold document pipeline with Parquet storage, document versioning, ingestion run tracking, Qdrant vector indexing, Redis query caching, and LangGraph-based retrieval grading and grounded answer generation.
```

---

## Final Release Target

Release tag:

```bash
git tag v2-release
```

Final target:

```text
RAGForge v2 should demonstrate both Data Engineering and AI Engineering skills:
- data modeling
- object storage
- Spark batch processing
- Parquet lakehouse-style layers
- Airflow orchestration
- Redis caching
- Qdrant vector retrieval
- LangGraph agentic RAG
- FastAPI platform APIs
```