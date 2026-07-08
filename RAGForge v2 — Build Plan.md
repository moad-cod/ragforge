

**Goal:** Evolve RAGForge from a RAG app into a full DE + agentic-RAG platform, adding: Data Modeling, Spark, Data Lakehouse (MinIO, Bronze/Silver/Gold), Airflow, Redis, and LangGraph — without Hadoop or Hive.

## Target Architecture


Documents → MinIO (Bronze, raw)
          → Spark job (clean, dedup, chunk)
          → MinIO (Silver, Parquet)
          → Embedding job
          → MinIO (Gold) + Qdrant (vectors) + Postgres (metadata)

Orchestration (offline/batch): Airflow DAGs
Orchestration (online/per-query): LangGraph agent graph
Cache/session/job-status: Redis
API: FastAPI (existing, extended)




## Week 1 — Data Foundation (Modeling → MinIO → Spark → Lakehouse)

### Day 1 — Data Modeling

- [ ] Audit current Postgres schema in RAGForge
- [ ] Design new schema: `documents`, `chunks`, `ingestion_runs`, `document_versions`, `query_logs`
- [ ] Add `document_version_id` for re-ingestion history (no silent overwrites)
- [ ] Write migration script (Alembic or raw SQL)
- [ ] Apply migration to local dev DB, verify with sample inserts

### Day 2 — MinIO Setup (replaces HDFS)

- [ ] Add MinIO service to `docker-compose.yml`
- [ ] Create buckets: `bronze`, `silver`, `gold`
- [ ] Configure `s3a`/boto3 client in the app to talk to MinIO
- [ ] Write small upload/download test script to confirm connectivity
- [ ] Document bucket structure in README (`bronze/{doc_id}/raw.*`)

### Day 3 — Bronze Layer: Raw Ingestion

- [ ] Update ingestion endpoint to write raw uploaded files to `bronze/` in MinIO
- [ ] Store ingestion metadata row in Postgres (`ingestion_runs`, status = `landed`)
- [ ] Test with 20-30 sample documents (PDF, txt, docx mix)
- [ ] Handle duplicate uploads (hash check before writing)

### Day 4-5 — Spark Batch Cleaning Job

- [ ] Set up local Spark (`local[*]` mode, no YARN)
- [ ] Write Spark job: read Bronze docs → clean text → dedup by content hash
- [ ] Chunk documents (reuse/adapt your existing chunking logic)
- [ ] Write cleaned chunks to `silver/` as Parquet
- [ ] Add corpus-level stats output (token count distribution, dedup rate, language detection)
- [ ] Run job end-to-end on the full sample set, verify Parquet output

### Day 6 — Silver → Gold: Embedding Job

- [ ] Write job that reads Silver Parquet chunks
- [ ] Generate embeddings (reuse existing embedding model/pipeline)
- [ ] Write enriched chunks + embeddings metadata to `gold/`
- [ ] Upsert vectors into Qdrant from Gold layer
- [ ] Update Postgres chunk/document status to `embedded`

### Day 7 — Buffer / Catch-up + Mini Review

- [ ] Fix any bugs from Days 1-6
- [ ] Write architecture diagram (Bronze/Silver/Gold + component map)
- [ ] Commit progress, tag `v2-week1` in git

---

## Week 2 — Orchestration, Caching, Agentic RAG

### Day 8 — Airflow Setup

- [ ] Add Airflow to `docker-compose.yml` (LocalExecutor, Postgres or SQLite backend — no Celery/Redis broker)
- [ ] Write DAG #1 — **Ingestion pipeline**: `new_document → Spark clean/chunk (Bronze→Silver) → embed (Silver→Gold) → upsert Qdrant → update Postgres`
- [ ] Test DAG manually with sample documents end-to-end

### Day 9 — Airflow: Maintenance DAG

- [ ] Write DAG #2 — **Corpus maintenance**: stale-document detection, re-embedding trigger, index refresh
- [ ] Schedule DAG #1 to trigger on new upload (sensor or API trigger), DAG #2 on a cron schedule
- [ ] Add basic data-quality checks (row counts Bronze vs Silver vs Gold, null checks)

### Day 10 — Redis Integration

- [ ] Add Redis service to `docker-compose.yml`
- [ ] Implement **query cache**: hash normalized query → cache RAG answer with TTL
- [ ] Implement **ingestion job status tracking**: `ingestion_job:{id}: status` for async upload progress
- [ ] (Optional) Implement conversation/session state in Redis for multi-turn chat
- [ ] Test cache hit/miss behavior, confirm FastAPI reads/writes correctly

### Day 11-12 — LangGraph Agentic RAG Loop

- [ ] Define graph state (query, retrieved_chunks, answer, retry_count)
- [ ] Node: Query Router (classify: retrieve / clarify / direct answer)
- [ ] Node: Retrieve (wrap your existing BM25 + dense + RRF + cross-encoder as a tool call)
- [ ] Node: Grade Relevance (LLM judges if retrieved chunks answer the query)
- [ ] Conditional edge: weak relevance → Rewrite Query → loop to Retrieve
- [ ] Node: Generate Answer
- [ ] Node: Grade Answer (groundedness/hallucination check vs retrieved chunks)
- [ ] Conditional edge: ungrounded → loop back to Generate/Retrieve (cap retries)
- [ ] Wire the graph into the FastAPI `/query` endpoint, replacing the old linear pipeline

### Day 13 — Integration Pass

- [ ] Full end-to-end test: upload doc → Airflow ingestion DAG → query via LangGraph → cached on repeat query
- [ ] Fix integration bugs (MinIO paths, Qdrant upserts, Redis keys)
- [ ] Add basic logging/tracing across the pipeline (ingestion + query paths)

### Day 14 — Docs, Diagram, Polish

- [ ] Update README: new architecture diagram, stack table, setup instructions
- [ ] Record a short demo (screen capture or GIF) of upload → query → cached repeat query
- [ ] Write a short "what changed from v1 to v2" section for the repo and for your CV/portfolio bullet
- [ ] Push final commit, tag `v2-release`

---

## Stack Summary (Final)

|Layer|Tool|
|---|---|
|Object storage|MinIO (S3-compatible)|
|Batch processing|Apache Spark (local mode)|
|Lakehouse layers|Bronze / Silver / Gold (Parquet on MinIO)|
|Orchestration (batch)|Apache Airflow|
|Orchestration (per-query)|LangGraph|
|Cache / session / job status|Redis|
|Vector search|Qdrant|
|Relational metadata|PostgreSQL|
|API|FastAPI|
|Containerization|Docker / Docker Compose|

**Dropped:** Hadoop, Hive — replaced by MinIO for the storage layer, since object storage is the current industry-standard pattern.