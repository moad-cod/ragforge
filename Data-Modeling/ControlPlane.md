# RAGForge v2 — Database Design Tasks

## Objective

Design and implement the PostgreSQL database for **RAGForge v2**, a Data Engineering + Agentic RAG platform.

The database must act as the **durable metadata source of truth** for:

* Projects
* Documents
* Document versions
* Ingestion runs
* Chunk metadata
* Embedding runs
* Query logs
* Retrieval logs

PostgreSQL should **not** store raw files, Parquet files, or vector embeddings directly.

Instead:

| Data                              | Stored In            |
| --------------------------------- | -------------------- |
| Raw uploaded files                | MinIO Bronze         |
| Cleaned chunks                    | MinIO Silver Parquet |
| Embedded chunk metadata           | MinIO Gold Parquet   |
| Vector embeddings                 | Qdrant               |
| Query cache / session / progress  | Redis                |
| Pipeline execution                | Airflow              |
| Metadata / status / audit history | PostgreSQL           |

---

# Core Database Questions

The database must be able to answer:

* Who uploaded the document?
* Which project does the document belong to?
* Which document version is currently active?
* Where is the raw file stored in Bronze?
* Where are cleaned chunks stored in Silver?
* Where is embedded metadata stored in Gold?
* Did ingestion succeed or fail?
* Which chunks were indexed in Qdrant?
* Which chunks were retrieved for a user query?
* Was the answer served from cache?

---

# Design Principles

## 1. PostgreSQL is the metadata source of truth

PostgreSQL stores:

* Document identity
* Version history
* Ingestion status
* Pipeline run history
* Chunk metadata
* Query history
* Retrieval history

## 2. MinIO stores document data

MinIO stores:

* Bronze raw files
* Silver cleaned chunk Parquet files
* Gold embedded chunk metadata Parquet files

PostgreSQL only stores paths to those objects.

## 3. Qdrant stores vectors

PostgreSQL stores only the `qdrant_point_id`.

The actual vector embeddings are stored in Qdrant.

## 4. Redis is temporary only

Redis can be used for:

* Query cache
* Session state
* Temporary ingestion progress
* Rate limits

Redis must not be the only durable source of truth for ingestion status.

## 5. Every upload creates a document version

A document can have many versions.

Re-uploading or re-ingesting a document must create a new `document_version_id`.

## 6. Qdrant must be rebuildable

Qdrant indexes must be rebuildable from Gold data and PostgreSQL metadata.

---

# Entity Relationship Overview

```text
users
  1 ──── * projects

organizations
  1 ──── * projects

projects
  1 ──── * documents
  1 ──── * ingestion_runs
  1 ──── * chunks
  1 ──── * query_logs

documents
  1 ──── * document_versions
  1 ──── * ingestion_runs
  1 ──── * chunks

document_versions
  1 ──── * ingestion_runs
  1 ──── * chunks
  1 ──── * embedding_runs

ingestion_runs
  1 ──── * chunks

query_logs
  1 ──── * retrieval_logs

chunks
  1 ──── * retrieval_logs
```

Most important relationship chain:

```text
documents.id
  → document_versions.document_id
  → ingestion_runs.document_version_id
  → chunks.document_version_id
  → chunks.qdrant_point_id
```

---

# Task 1 — Create Core Application Tables

## Goal

Create the base application tables required to support ownership, multi-tenancy, and project-level isolation.

## Tables

* `organizations`
* `users`
* `projects`

---

## 1.1 Table: `organizations`

### Purpose

Stores organizations or tenants.

Use this table if the platform supports multi-tenancy.

### Schema

```text
organizations
- id UUID primary key
- name text not null
- created_at timestamp not null
- updated_at timestamp not null
- deleted_at timestamp nullable
```

### Acceptance Criteria

* Organization records can be created.
* Organization deletion is soft delete using `deleted_at`.
* Projects can reference an organization.

---

## 1.2 Table: `users`

### Purpose

Stores users who upload documents, create projects, and ask questions.

### Schema

```text
users
- id UUID primary key
- organization_id UUID nullable
- email text unique not null
- full_name text nullable
- created_at timestamp not null
- updated_at timestamp not null
- deleted_at timestamp nullable
```

### Constraints

```text
foreign key organization_id references organizations(id)
unique(email)
```

### Acceptance Criteria

* Each user has a unique email.
* Users can optionally belong to an organization.
* User deletion is soft delete using `deleted_at`.

---

## 1.3 Table: `projects`

### Purpose

Groups documents, queries, user access, and Qdrant filtering.

Every document and query must belong to a project.

### Schema

```text
projects
- id UUID primary key
- organization_id UUID nullable
- name text not null
- qdrant_collection text unique not null
- created_by UUID not null
- created_at timestamp not null
- updated_at timestamp not null
- deleted_at timestamp nullable
```

### Important Rule

Do not generate Qdrant collection names from project names.

Use immutable IDs.

Recommended format:

```text
project_{project_id}
```

### Constraints

```text
foreign key organization_id references organizations(id)
foreign key created_by references users(id)
unique(qdrant_collection)
```

### Indexes

```text
projects(organization_id)
projects(created_by)
projects(created_at)
projects(deleted_at)
```

### Acceptance Criteria

* A project can be created by a user.
* A project can belong to an organization.
* Each project has a unique Qdrant collection name.
* Project deletion is handled by soft delete.

---

# Task 2 — Create `documents` Table

## Goal

Create the logical document table.

A document represents the business object, not a specific uploaded file version.

Example:

```text
report.pdf
```

If the user uploads a new version of `report.pdf`, the `documents` row stays the same, but a new `document_versions` row is created.

---

## Table: `documents`

### Purpose

Stores logical document records.

### Schema

```text
documents
- id UUID primary key
- project_id UUID not null
- current_version_id UUID nullable
- source_type text
- filename text
- mime_type text
- extension text
- status text not null
- created_by UUID not null
- created_at timestamp not null
- updated_at timestamp not null
- deleted_at timestamp nullable
```

### Recommended Status Values

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

### Meaning

```text
documents = logical business object
document_versions = physical uploaded or processed version
```

### Constraints

```text
foreign key project_id references projects(id)
foreign key created_by references users(id)
```

Add the `current_version_id` foreign key after `document_versions` is created to avoid circular migration issues.

Later:

```text
foreign key current_version_id references document_versions(id)
```

### Indexes

```text
documents(project_id)
documents(current_version_id)
documents(status)
documents(created_by)
documents(created_at)
documents(deleted_at)
```

### Acceptance Criteria

* A document belongs to exactly one project.
* A document can have one active current version.
* A document can be soft deleted.
* Document status can track the latest lifecycle state.

---

# Task 3 — Create `document_versions` Table

## Goal

Track every upload and re-ingestion of a document.

Every upload must create a new `document_version_id`.

This prevents silent overwrites and supports:

* Version history
* Re-ingestion
* Debugging
* Auditability
* Qdrant rebuilds
* Embedding model comparison
* Chunking strategy comparison

---

## Table: `document_versions`

### Purpose

Stores physical document version metadata.

### Schema

```text
document_versions
- id UUID primary key
- document_id UUID not null
- version_number int not null
- content_hash text not null
- bronze_path text
- silver_path text
- gold_path text
- parser_name text
- chunker_id text
- embedding_model text
- status text not null
- error_message text nullable
- created_at timestamp not null
```

### Path Meaning

```text
bronze_path = raw file location in MinIO Bronze
silver_path = cleaned chunks Parquet location in MinIO Silver
gold_path   = embedded metadata Parquet location in MinIO Gold
```

Example:

```text
bronze/org_id=org_123/project_id=proj_456/document_id=doc_789/version=1/raw/report.pdf
silver/org_id=org_123/project_id=proj_456/document_id=doc_789/version=1/chunks.parquet
gold/org_id=org_123/project_id=proj_456/document_id=doc_789/version=1/embedded_chunks.parquet
```

### Constraints

```text
foreign key document_id references documents(id)
unique(document_id, version_number)
unique(document_id, content_hash)
```

### Indexes

```text
document_versions(document_id)
document_versions(status)
document_versions(content_hash)
document_versions(created_at)
```

### Acceptance Criteria

* A document can have multiple versions.
* Version numbers must be unique per document.
* Content hashes must be unique per document.
* Bronze, Silver, and Gold paths can be stored.
* Failed versions can store an error message.

---

# Task 4 — Add `current_version_id` Relationship

## Goal

Connect `documents.current_version_id` to `document_versions.id`.

This should be done after both tables exist.

---

## Migration Step

Add foreign key:

```text
documents.current_version_id → document_versions.id
```

### Acceptance Criteria

* Each document can point to its active version.
* Old versions remain available.
* Updating the active version does not delete historical versions.

---

# Task 5 — Create `ingestion_runs` Table

## Goal

Track every ingestion pipeline execution.

A document version can have multiple ingestion runs.

Example:

```text
version 1
  → ingestion run 1 failed
  → ingestion run 2 succeeded
```

This gives the platform full pipeline auditability.

---

## Table: `ingestion_runs`

### Purpose

Stores ingestion pipeline execution history.

### Schema

```text
ingestion_runs
- id UUID primary key
- project_id UUID not null
- document_id UUID not null
- document_version_id UUID not null
- status text not null
- started_at timestamp nullable
- finished_at timestamp nullable
- error_message text nullable
- airflow_dag_run_id text nullable
- created_by UUID not null
- created_at timestamp not null
```

### Recommended Status Values

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

### Constraints

```text
foreign key project_id references projects(id)
foreign key document_id references documents(id)
foreign key document_version_id references document_versions(id)
foreign key created_by references users(id)
```

### Indexes

```text
ingestion_runs(project_id)
ingestion_runs(document_id)
ingestion_runs(document_version_id)
ingestion_runs(status)
ingestion_runs(created_at)
ingestion_runs(airflow_dag_run_id)
```

### Acceptance Criteria

* Every file upload creates an ingestion run.
* Upload endpoint returns immediately after creating the run.
* Long processing happens asynchronously through Airflow and Spark.
* Failed runs preserve error messages.
* Airflow DAG run IDs can be stored for traceability.

---

# Task 6 — Create `chunks` Table

## Goal

Store chunk metadata in PostgreSQL.

Important:

PostgreSQL stores chunk metadata, not vector embeddings.

The vector embedding is stored in Qdrant.

Silver and Gold Parquet files are stored in MinIO.

---

## Table: `chunks`

### Purpose

Stores searchable and traceable chunk metadata.

### Schema

```text
chunks
- id UUID primary key
- project_id UUID not null
- document_id UUID not null
- document_version_id UUID not null
- ingestion_run_id UUID nullable
- qdrant_point_id text unique
- chunk_index int not null
- text text not null
- content_hash text not null
- token_count int nullable
- page_start int nullable
- page_end int nullable
- section_title text nullable
- metadata_json jsonb
- created_at timestamp not null
```

### Qdrant Point Lineage Rule

Build the deterministic readable lineage key:

```text
{document_version_id}:{chunk_index}
```

Example:

```text
550e8400-e29b-41d4-a716-446655440000:12
```

Store this value as `lineage_id` in the Qdrant payload and derive the actual
Qdrant/PostgreSQL point ID as UUIDv5, because Qdrant point IDs must be unsigned
integers or UUIDs. This makes Qdrant indexing:

* Idempotent
* Rebuildable
* Easy to debug

### Constraints

```text
foreign key project_id references projects(id)
foreign key document_id references documents(id)
foreign key document_version_id references document_versions(id)
foreign key ingestion_run_id references ingestion_runs(id)

unique(qdrant_point_id)
unique(document_version_id, chunk_index)
unique(document_version_id, content_hash)
```

### Indexes

```text
chunks(project_id)
chunks(document_id)
chunks(document_version_id)
chunks(ingestion_run_id)
chunks(qdrant_point_id)
chunks(content_hash)
chunks(created_at)
chunks(project_id, document_id)
chunks(document_version_id, chunk_index)
```

### Acceptance Criteria

* Each chunk belongs to a project.
* Each chunk belongs to a document.
* Each chunk belongs to a document version.
* Each chunk can be linked to an ingestion run.
* Duplicate chunks can be detected by `content_hash`.
* Qdrant point IDs are unique.
* Chunk indexes are unique per document version.

---

# Task 7 — Create `embedding_runs` Table

## Goal

Track embedding generation for each document version.

This supports:

* Embedding job monitoring
* Model comparison
* Failed embedding retries
* Evaluation experiments

---

## Table: `embedding_runs`

### Purpose

Stores embedding generation history.

### Schema

```text
embedding_runs
- id UUID primary key
- project_id UUID not null
- document_version_id UUID not null
- embedding_model text not null
- status text not null
- total_chunks int default 0
- embedded_chunks int default 0
- started_at timestamp nullable
- finished_at timestamp nullable
- error_message text nullable
- created_at timestamp not null
```

### Constraint

```text
foreign key project_id references projects(id)
foreign key document_version_id references document_versions(id)
unique(document_version_id, embedding_model)
```

### Indexes

```text
embedding_runs(project_id)
embedding_runs(document_version_id)
embedding_runs(embedding_model)
embedding_runs(status)
embedding_runs(created_at)
```

### Acceptance Criteria

* Embedding progress can be tracked.
* Failed embedding jobs store error messages.
* The same document version can be embedded with different models.
* The same document version and model combination cannot be duplicated.

---

# Task 8 — Create `query_logs` Table

## Goal

Track user queries for observability, debugging, cache analysis, and RAG evaluation.

This table should support both:

* Classic `/rag/query`
* Agentic `/rag/agent-query`

---

## Table: `query_logs`

### Purpose

Stores user question metadata.

### Schema

```text
query_logs
- id UUID primary key
- project_id UUID not null
- user_id UUID not null
- question text not null
- normalized_question_hash text
- provider text
- model text
- latency_ms int nullable
- cache_hit boolean default false
- route text nullable
- relevance_score float nullable
- groundedness_score float nullable
- created_at timestamp not null
```

### Field Meaning

```text
question = original user question
normalized_question_hash = stable hash used for cache lookup
provider = llm provider, example: gemini, groq
model = llm model name
latency_ms = total response time
cache_hit = whether Redis returned cached answer
route = agent route, example: direct_answer, clarify, retrieve
relevance_score = retrieval relevance grade
groundedness_score = answer groundedness grade
```

### Constraints

```text
foreign key project_id references projects(id)
foreign key user_id references users(id)
```

### Indexes

```text
query_logs(project_id)
query_logs(user_id)
query_logs(normalized_question_hash)
query_logs(created_at)
query_logs(project_id, created_at)
```

### Acceptance Criteria

* Every RAG query can be logged.
* Cache hits and misses can be measured.
* Agentic routing decisions can be stored.
* Relevance and groundedness scores can be analyzed later.

---

# Task 9 — Create `retrieval_logs` Table

## Goal

Track which chunks were retrieved for each query.

This is critical for RAG debugging and evaluation.

---

## Table: `retrieval_logs`

### Purpose

Stores retrieval trace records.

### Schema

```text
retrieval_logs
- id UUID primary key
- query_log_id UUID not null
- chunk_id UUID nullable
- qdrant_score float nullable
- rerank_score float nullable
- rank int not null
- retrieval_strategy text
- used_in_answer boolean default false
- created_at timestamp not null
```

### Field Meaning

```text
query_log_id = query that triggered retrieval
chunk_id = retrieved chunk from PostgreSQL
qdrant_score = similarity score from Qdrant
rerank_score = score from reranker model
rank = retrieval position
retrieval_strategy = dense, sparse, hybrid, rerank, agentic
used_in_answer = whether the chunk was used in final answer
```

### Constraints

```text
foreign key query_log_id references query_logs(id)
foreign key chunk_id references chunks(id)
```

### Indexes

```text
retrieval_logs(query_log_id)
retrieval_logs(chunk_id)
retrieval_logs(rank)
retrieval_logs(query_log_id, rank)
```

### Acceptance Criteria

* Each query can have many retrieval logs.
* Retrieved chunks can be ranked.
* Qdrant and rerank scores can be stored.
* The system can identify which chunks were used in the final answer.

---

# Task 10 — Add Status Validation

## Goal

Prevent invalid status values from being stored.

Use either PostgreSQL enums or application-level validation.

For flexibility during development, application-level validation is acceptable.

For stricter production design, use PostgreSQL enums.

---

## Document Status Values

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

## Ingestion Run Status Values

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

## Recommended Embedding Run Status Values

```text
queued
running
completed
failed
cancelled
```

### Acceptance Criteria

* Invalid document statuses are rejected.
* Invalid ingestion statuses are rejected.
* Invalid embedding statuses are rejected.
* Status transitions are handled consistently by the application.

---

# Task 11 — Add Database Indexes

## Goal

Improve query performance for document filtering, ingestion monitoring, chunk lookup, and RAG observability.

---

## Required Indexes

```text
documents(project_id)
documents(current_version_id)
documents(status)
documents(created_by)
documents(created_at)

document_versions(document_id)
document_versions(status)
document_versions(content_hash)
document_versions(created_at)

ingestion_runs(project_id)
ingestion_runs(document_id)
ingestion_runs(document_version_id)
ingestion_runs(status)
ingestion_runs(created_at)

chunks(project_id)
chunks(document_id)
chunks(document_version_id)
chunks(qdrant_point_id)
chunks(content_hash)
chunks(created_at)

query_logs(project_id)
query_logs(user_id)
query_logs(normalized_question_hash)
query_logs(created_at)

retrieval_logs(query_log_id)
retrieval_logs(chunk_id)
retrieval_logs(rank)
```

---

## High-Priority RAG Indexes

```text
chunks(project_id, document_id)
chunks(document_version_id, chunk_index)
query_logs(project_id, created_at)
retrieval_logs(query_log_id, rank)
```

### Acceptance Criteria

* Project document lookup is fast.
* Chunk lookup by document version is fast.
* Query history by project is fast.
* Retrieval trace lookup by query is fast.

---

# Task 12 — Add Alembic Migration

## Goal

Create a database migration for the full schema.

---

## Required Migration Files

Create one Alembic migration for:

```text
organizations
users
projects
documents
document_versions
ingestion_runs
chunks
embedding_runs
query_logs
retrieval_logs
indexes
constraints
foreign keys
```

Recommended command:

```bash
cd backend
alembic revision -m "create_ragforge_v2_database_schema"
```

Then implement the schema manually inside the generated migration file.

Apply migration:

```bash
alembic upgrade head
```

### Acceptance Criteria

* Migration runs successfully from an empty database.
* Migration creates all tables.
* Migration creates all constraints.
* Migration creates all indexes.
* Migration can be rolled back.

---

# Task 13 — Add SQLAlchemy Models

## Goal

Add ORM models that match the database schema.

---

## File

```text
backend/app/models/tables.py
```

## Models to Implement

```text
Organization
User
Project
Document
DocumentVersion
IngestionRun
Chunk
EmbeddingRun
QueryLog
RetrievalLog
```

### Acceptance Criteria

* SQLAlchemy models match the Alembic schema.
* Relationships are defined between models.
* UUID primary keys are supported.
* JSONB is used for `metadata_json`.
* Timestamp fields are handled consistently.

---

# Task 14 — Add Repository / CRUD Layer

## Goal

Create reusable database functions so API routes and jobs do not write raw SQL everywhere.

---

## Recommended File Structure

```text
backend/app/repositories/
  projects.py
  documents.py
  document_versions.py
  ingestion_runs.py
  chunks.py
  embedding_runs.py
  query_logs.py
  retrieval_logs.py
```

---

## Required Functions

### Documents

```text
create_document()
get_document()
list_project_documents()
update_document_status()
set_current_version()
soft_delete_document()
```

### Document Versions

```text
create_document_version()
get_document_version()
get_latest_version_number()
update_version_paths()
update_version_status()
```

### Ingestion Runs

```text
create_ingestion_run()
get_ingestion_run()
update_ingestion_status()
mark_ingestion_failed()
list_failed_runs()
list_stuck_runs()
```

### Chunks

```text
bulk_insert_chunks()
get_chunks_by_document_version()
get_chunk_by_qdrant_point_id()
delete_chunks_by_document_version()
```

### Embedding Runs

```text
create_embedding_run()
update_embedding_progress()
mark_embedding_completed()
mark_embedding_failed()
```

### Query Logs

```text
create_query_log()
update_query_scores()
get_project_query_history()
```

### Retrieval Logs

```text
bulk_insert_retrieval_logs()
get_retrieval_logs_for_query()
```

### Acceptance Criteria

* API routes use repository functions.
* Airflow/Spark jobs use repository functions.
* Database logic is not duplicated across the codebase.
* Repository functions are unit-testable.

---

# Task 15 — Update Upload Flow

## Goal

Change upload behavior from synchronous processing to asynchronous ingestion.

---

## Old Behavior

```text
upload → parse → chunk → embed → index inside request
```

## New Behavior

```text
upload
  → create document
  → create document version
  → upload raw file to MinIO Bronze
  → create ingestion run with status = landed
  → return immediately
```

---

## Endpoint

```text
POST /ingest/file
```

## Response

```json
{
  "document_id": "uuid",
  "document_version_id": "uuid",
  "ingestion_run_id": "uuid",
  "status": "landed"
}
```

### Acceptance Criteria

* Upload does not process large documents synchronously.
* Raw file is stored in Bronze.
* `documents` row is created.
* `document_versions` row is created.
* `ingestion_runs` row is created.
* Response returns `ingestion_run_id`.

---

# Task 16 — Add Ingestion Status Endpoint

## Goal

Expose ingestion progress to the frontend and API consumers.

---

## Endpoint

```text
GET /ingest/runs/{ingestion_run_id}
```

## Response

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

### Acceptance Criteria

* Status is read from PostgreSQL.
* Redis can be used as a temporary progress cache.
* PostgreSQL remains the durable source of truth.
* Endpoint returns Bronze/Silver/Gold/Qdrant progress.

---

# Task 17 — Connect Database to Airflow Jobs

## Goal

Allow Airflow tasks to update PostgreSQL status during the ingestion pipeline.

---

## Pipeline Status Flow

```text
landed
  → queued
  → running
  → silver_completed
  → gold_completed
  → indexed
```

On failure:

```text
failed
```

---

## Airflow Tasks

```text
validate_bronze
bronze_to_silver_spark
silver_to_gold_embed
upsert_qdrant
update_postgres_status
```

### Acceptance Criteria

* Airflow can read ingestion run metadata.
* Airflow updates run status after each step.
* Failed jobs update `error_message`.
* `airflow_dag_run_id` is stored in `ingestion_runs`.

---

# Task 18 — Connect Chunks to Qdrant

## Goal

Ensure every indexed chunk has a stable Qdrant point ID.

---

## Qdrant Point Lineage Format

```text
{document_version_id}:{chunk_index}
```

Qdrant accepts unsigned integers or UUIDs as point IDs, so this readable value
is stored as `lineage_id` in the point payload. The actual `qdrant_point_id`
stored in Qdrant and PostgreSQL is a deterministic UUIDv5 derived from this
lineage value. This preserves idempotency while using a Qdrant-valid ID.

## Qdrant Payload

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

### Acceptance Criteria

* Each PostgreSQL chunk has a `qdrant_point_id`.
* Each Qdrant point payload includes project and document metadata.
* Every query filters by `project_id`.
* Qdrant can be rebuilt from Gold and PostgreSQL metadata.

---

# Task 19 — Add Query Logging

## Goal

Log every RAG query for debugging, analytics, and evaluation.

---

## Required Behavior

When `/rag/query` or `/rag/agent-query` is called:

1. Normalize the question.
2. Hash the normalized question.
3. Check Redis cache.
4. Create a `query_logs` row.
5. Run retrieval or direct answer logic.
6. Store latency.
7. Store cache hit or miss.
8. Store agent scores if available.

### Acceptance Criteria

* Every query creates a `query_logs` row.
* Cache hits are recorded.
* Provider and model are recorded.
* Latency is recorded.
* Agentic route and scores are recorded when available.

---

# Task 20 — Add Retrieval Logging

## Goal

Store which chunks were retrieved for each query.

---

## Required Behavior

For each retrieved chunk, insert a `retrieval_logs` row with:

```text
query_log_id
chunk_id
qdrant_score
rerank_score
rank
retrieval_strategy
used_in_answer
```

### Acceptance Criteria

* Each query can be traced to retrieved chunks.
* Retrieval rank is stored.
* Qdrant score is stored.
* Rerank score is stored when available.
* Chunks used in the final answer are marked.

---

# Task 21 — Add Seed Data and Validation Tests

## Goal

Verify the database schema works before connecting the full platform.

---

## Required Tests

### Project Test

* Create organization.
* Create user.
* Create project.
* Verify Qdrant collection name is unique.

### Document Test

* Create document.
* Create document version.
* Set document current version.
* Verify relationships.

### Ingestion Test

* Create ingestion run.
* Update status from `landed` to `indexed`.
* Verify timestamps and error handling.

### Chunk Test

* Insert chunks.
* Verify unique `chunk_index` per document version.
* Verify duplicate `content_hash` is rejected.
* Verify `qdrant_point_id` is unique.

### Query Test

* Create query log.
* Insert retrieval logs.
* Verify retrieval logs link to chunks.

### Acceptance Criteria

* All tests pass locally.
* Invalid foreign keys are rejected.
* Duplicate records are rejected where expected.
* Query and retrieval logs are correctly linked.

---

# Task 22 — Final Database Validation Checklist

Before considering the database complete, verify:

```text
[ ] All core tables exist.
[ ] All foreign keys exist.
[ ] All unique constraints exist.
[ ] All required indexes exist.
[ ] Document versioning works.
[ ] Ingestion run tracking works.
[ ] Chunk metadata insertion works.
[ ] Qdrant point IDs are deterministic.
[ ] Query logging works.
[ ] Retrieval logging works.
[ ] MinIO paths are stored correctly.
[ ] Redis is not used as durable truth.
[ ] Qdrant can be rebuilt from Gold data.
[ ] Alembic migration runs successfully.
[ ] Alembic rollback works.
[ ] Seed tests pass.
```

---

# Recommended Implementation Order for AI Agent

Use this order when asking an AI coding agent to build the database:

```text
1. Create Alembic migration for organizations, users, and projects.
2. Create documents table.
3. Create document_versions table.
4. Add current_version_id foreign key to documents.
5. Create ingestion_runs table.
6. Create chunks table.
7. Create embedding_runs table.
8. Create query_logs table.
9. Create retrieval_logs table.
10. Add all indexes.
11. Add SQLAlchemy models.
12. Add repository/CRUD functions.
13. Update upload endpoint to create document, version, and ingestion run.
14. Add ingestion status endpoint.
15. Connect Airflow jobs to ingestion status updates.
16. Connect Qdrant point IDs to chunk records.
17. Add query logging.
18. Add retrieval logging.
19. Add seed data.
20. Add validation tests.
```

---

# Final Design Summary

RAGForge v2 database design separates the platform into clear responsibility layers:

```text
documents = logical document identity
document_versions = physical uploaded/processed versions
ingestion_runs = pipeline execution history
chunks = searchable chunk metadata
embedding_runs = embedding generation history
query_logs = user query observability
retrieval_logs = retrieval evaluation and debugging
```

This design is stronger than a simple RAG schema with only:

```text
documents
chunks
```

Because RAGForge v2 needs production-style capabilities:

* Re-ingestion
* Version history
* Pipeline retries
* Auditability
* Qdrant rebuilds
* Cache tracking
* Query evaluation
* Retrieval debugging
* Multi-model embedding comparison
* Agentic RAG observability

The final database should support both Data Engineering and AI Engineering use cases while remaining clean, scalable, and production-ready.
