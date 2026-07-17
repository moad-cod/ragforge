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
- answer text nullable
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
answer = final durable answer for completed classic or streaming queries
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

## Implementation Status — Complete (2026-07-13)

`backend/seed_control_plane.py` creates a deterministic, idempotent graph that
includes every control-plane table. The `backend/tests/test_control_plane_database.py`
suite runs against a protected database whose name must end in `_test`; it
validates the relationships and rejection cases above using PostgreSQL rather
than mocks.

```bash
cd backend
RUN_DATABASE_TESTS=1 python -m unittest tests.test_control_plane_database -v
```

---

# Task 22 — Final Database Validation Checklist

Before considering the database complete, verify:

```text
[x] All core tables exist.
[x] All foreign keys exist.
[x] All unique constraints exist.
[x] All required indexes exist.
[x] Document versioning works.
[x] Ingestion run tracking works.
[x] Chunk metadata insertion works.
[x] Qdrant point IDs are deterministic.
[x] Query logging works.
[x] Retrieval logging works.
[x] MinIO paths are stored correctly.
[x] Redis is not used as durable truth.
[x] Qdrant can be rebuilt from Gold data.
[x] Alembic migration runs successfully.
[x] Alembic rollback works.
[x] Seed tests pass.
```

## Implementation Status — Complete (2026-07-13)

`backend/validate_control_plane.py` uses live database introspection to validate
the structural portion of this checklist. The Task 21 PostgreSQL integration
suite validates the behavioral portion and performs the reversible Alembic
migration cycle. Task 18 lineage tests cover deterministic Qdrant rebuilds;
Tasks 19–20 tests cover durable query and retrieval logging when Redis is
unavailable.

---

# Task 23 — Add Real-Time Progress and Query Streaming

## Goal

Expose truthful, authenticated progress events so the frontend can explain
long-running ingestion and retrieval work with a ChatGPT-style experience.

The UI may animate the active stage and show elapsed time, but it must not
invent completion percentages or report a stage as complete before the backend
has durably crossed that boundary.

---

## Source of Truth

```text
PostgreSQL = durable operation status and final timestamps
Redis      = temporary event stream, fan-out, and short replay window
SSE        = authenticated server-to-client delivery
```

Redis must never become the only record of ingestion completion or failure. If
Redis is unavailable or an event expires, the API reconstructs the latest
ingestion state from PostgreSQL and clients continue through polling or a fresh
stream snapshot.

---

## Streaming Endpoints

```text
GET  /ingest/runs/{ingestion_run_id}/events
POST /rag/query/stream
```

Both endpoints require the normal user JWT. The ingestion stream verifies that
the current user owns the ingestion run. Query streaming applies the same
project and optional document ownership checks as `POST /rag/query`.

Use Server-Sent Events over a streaming `fetch` response. Authentication tokens
must be sent in headers, not query parameters. WebSockets are not required for
this one-way event flow.

---

## Common Event Envelope

Every event uses a stable envelope:

```json
{
  "event_id": "operation_uuid:sequence",
  "operation_id": "ingestion_run_or_query_log_uuid",
  "type": "ingestion.chunking",
  "stage": "chunking",
  "message": "Document divided into searchable sections",
  "timestamp": "2026-07-12T16:30:00Z",
  "progress": {
    "current": 18,
    "total": 42,
    "unit": "pages"
  },
  "data": {}
}
```

`progress` is optional. It is emitted only when `current` and `total` come from
real pipeline measurements. Otherwise the frontend displays a stage indicator
and elapsed time without a fabricated percentage.

---

## Ingestion Events

```text
ingestion.snapshot
ingestion.landed
ingestion.queued
ingestion.running
ingestion.parsing
ingestion.chunking
ingestion.embedding
ingestion.indexing
ingestion.completed
ingestion.failed
ingestion.cancelled
```

Durable status mapping:

```text
landed            → ingestion.landed
queued            → ingestion.queued
running           → ingestion.running / parsing
silver_completed  → ingestion.chunking completed
gold_completed    → ingestion.embedding completed
indexed           → ingestion.completed
failed            → ingestion.failed
cancelled         → ingestion.cancelled
```

Detailed page/chunk counters may be published between durable boundaries, but
the corresponding PostgreSQL status is still the recovery source of truth.

---

## Query Events

```text
query.received
query.embedding
query.retrieving
query.reranking
query.generating
query.token
query.completed
query.failed
```

`query.token` carries only the next generated text fragment. `query.completed`
contains the final model, provider, latency, cache-hit state, and optional
context allowed by the request. Tasks 19 and 20 persist the final query and
retrieval trace even if the client disconnects before receiving the last event.

The non-streaming `POST /rag/query` endpoint remains available for simple API
clients and uses the same retrieval/generation service as the streaming route.

---

## Reconnection and Recovery

* Send an initial `snapshot` event immediately after authorization.
* Give every event a monotonically increasing sequence within its operation.
* Accept `Last-Event-ID` when the client reconnects.
* Replay retained Redis Stream events after that ID when available.
* Fall back to a PostgreSQL snapshot when replay is unavailable.
* Send an SSE heartbeat at least every 15 seconds while no work event is emitted.
* Close the stream after a terminal `completed`, `failed`, or `cancelled` event.
* Query generation continues to its logging boundary if the browser disconnects.

---

## Frontend Behavior Contract

The frontend may present messages such as:

```text
Uploading document…
Saving the original file…
Extracting and splitting content…
Creating search embeddings…
Building the search index…
Document ready
```

For queries:

```text
Understanding your question…
Searching relevant sections…
Ranking the best evidence…
Generating an answer…
```

Completed stages receive check marks, the active stage may animate, and elapsed
time is calculated client-side. The UI must show the backend error message and
retry affordance for failed operations.

---

## Required Tests

* Users cannot subscribe to another tenant's ingestion events.
* The first ingestion event reflects the current PostgreSQL status.
* Ingestion events follow valid lifecycle order.
* Duplicate/replayed event IDs are safe for clients to ignore.
* Reconnection with `Last-Event-ID` replays available events.
* Missing Redis history falls back to a durable PostgreSQL snapshot.
* Query stage events are emitted in order.
* Generated tokens reconstruct the final persisted answer.
* Query and retrieval logs are completed after client disconnect.
* Failed ingestion and query operations emit one terminal failure event.
* Heartbeats keep long-running streams open without changing operation status.

### Acceptance Criteria

* The frontend can display real ingestion stages without guessing state.
* Query answers stream token by token.
* Refreshing or reconnecting does not lose durable progress.
* Redis failure does not erase or corrupt operation status.
* All streaming endpoints enforce tenant ownership.
* Streaming and non-streaming query routes share the same business logic.
* Task 19 query latency and Task 20 retrieval traces remain accurate.

## Implementation Status — Complete (2026-07-13)

`GET /ingest/runs/{ingestion_run_id}/events` sends an authenticated PostgreSQL
snapshot first, replays newer Redis Stream events after `Last-Event-ID`, polls
durable state when replay is missing, emits idle heartbeats, and closes on a
terminal status. Upload, Airflow enqueue, and internal pipeline transitions all
publish best-effort events after their database transaction commits.

`POST /rag/query/stream` and `POST /rag/query` call the same query executor.
The streaming route emits ordered stage events and model fragments, while its
worker owns an independent database session so disconnecting the browser does
not cancel query/retrieval logging. Revision `20260713_0002` adds the durable
`query_logs.answer` column used to verify that streamed tokens reconstruct the
stored final answer.

```bash
cd backend
python -m unittest tests.test_realtime_streaming -v
RUN_REDIS_TESTS=1 python -m unittest tests.test_realtime_streaming.RedisEventIntegrationTests -v
```

---

# Remaining Control-Plane Delivery Work

Tasks 1–23 complete the control-plane implementation. The following tasks move
that implementation onto the shared development baseline, connect it to real
data-plane commands, validate the whole platform, expose it in the frontend,
and prepare it for production. These tasks are not complete unless their
acceptance criteria have been exercised against running services.

---

# Task 24 — Integrate the Completed Control Plane

## Goal

Merge the completed Task 18–23 feature branches into `dev` and establish one
tested integration baseline without losing local runtime configuration.

## Required Work

* Open and review pull requests for the completed feature branches.
* Merge the branches into `dev` in dependency order.
* Resolve migration, Docker Compose, Airflow, and documentation conflicts.
* Run the complete backend test suite from the merged `dev` branch.
* Run `alembic upgrade head` against a clean development database.
* Keep `.env` files and credentials untracked; update `.env.example` only with
  safe placeholders and documented defaults.

### Acceptance Criteria

* `dev` contains Tasks 1–23 and has a clean working tree.
* The Alembic revision chain has one valid head.
* Docker Compose configuration renders successfully.
* All unit, PostgreSQL integration, and Redis integration tests pass.
* No API keys, passwords, tokens, or local `.env` files are committed.

## Implementation Status — Planned

---

# Task 25 — Wire the Real Airflow Data Pipeline

## Goal

Replace the empty Airflow command placeholders with executable,
container-safe Bronze-to-Silver, Silver-to-Gold, and Qdrant indexing commands.

## Required Work

Configure and test:

```text
RAGFORGE_BRONZE_TO_SILVER_CMD
RAGFORGE_SILVER_TO_GOLD_CMD
RAGFORGE_UPSERT_QDRANT_CMD
```

Each command must accept `{ingestion_run_id}`, read its input location from the
control-plane metadata, produce the expected artifact or index state, and exit
non-zero on failure. The commands must be valid inside the Airflow containers;
host-only paths and `localhost` service URLs are not acceptable there.

The pipeline must also:

* Write Silver chunk Parquet data to the version's `silver_path`.
* Write Gold embedded metadata to the version's `gold_path`.
* Index deterministic Task 18 points in the project Qdrant collection.
* Update PostgreSQL only after the corresponding data-plane write succeeds.
* Preserve idempotency when an Airflow task or DAG run is retried.
* Store task or DAG failure details in `ingestion_runs.error_message`.

### Acceptance Criteria

* A real uploaded document advances through every durable ingestion status.
* Silver and Gold artifacts exist and match their PostgreSQL paths.
* PostgreSQL chunk rows match the indexed Qdrant points.
* Retrying the same run does not duplicate artifacts, chunks, or vector points.
* A forced command failure produces a durable `failed` status and useful error.

## Implementation Status — Complete (2026-07-14)

The Airflow batch image now contains the parser, Parquet, embedding, and MinIO
dependencies required by three built-in container commands:

```text
python -m jobs.bronze_to_silver --ingestion-run-id {ingestion_run_id}
python -m jobs.silver_to_gold --ingestion-run-id {ingestion_run_id}
python -m jobs.upsert_qdrant --ingestion-run-id {ingestion_run_id}
```

Bronze-to-Silver parses the versioned MinIO object, applies the selected
chunker, and overwrites deterministic Silver Parquet. Silver-to-Gold embeds
those rows and overwrites deterministic Gold Parquet. Gold indexing reads the
artifact and calls the authenticated Task 18 boundary, which replaces the
version's deterministic Qdrant points and PostgreSQL chunk rows.

Airflow records `silver_path` and `gold_path` in the same durable transition
that advances each status, and task failures persist the command error. The
Airflow 3.3 trigger request includes its required nullable `logical_date`.

A live Docker Compose validation uploaded a text document and exercised
PostgreSQL, MinIO, Airflow, Qdrant, and Redis through `indexed`. Both Parquet
objects existed at the recorded paths, PostgreSQL and Qdrant contained the
same deterministic chunk lineage, rerunning all three commands retained one
artifact per layer and one chunk/point, and a controlled empty-document run
ended durably in `failed` with a useful `No indexable text` error.

---

# Task 26 — Add Full End-to-End Control-Plane Tests

## Goal

Prove that the API, PostgreSQL, MinIO, Airflow, Qdrant, Redis, and model provider
work together through real user flows.

## Required Scenarios

1. Upload a representative document through `POST /ingest/file`.
2. Confirm the Bronze object, document version, and landed ingestion run.
3. Confirm Airflow processes the run through Silver, Gold, and Qdrant.
4. Observe ordered ingestion SSE events through the terminal state.
5. Query the indexed project using both streaming and non-streaming routes.
6. Verify the answer, query log, retrieval ranks, and chunk lineage.
7. Restart or disable Redis and verify PostgreSQL snapshot recovery.
8. Force pipeline and provider failures and verify durable failure behavior.
9. Verify that one tenant cannot access another tenant's runs or queries.

### Acceptance Criteria

* The complete upload-to-answer flow passes using running containers.
* Stored paths, statuses, timestamps, counts, and lineage agree across systems.
* Streaming events agree with durable PostgreSQL state.
* Redis loss does not lose completed work or corrupt query/ingestion state.
* The critical path is automated in a repeatable integration test or CI job.

## Implementation Status — Complete (2026-07-16)

Task 26 adds an isolated `ragforge-e2e` Docker Compose project and a one-command
`make e2e-v2` runner. The suite applies Alembic migrations to clean PostgreSQL
and Airflow databases, starts MinIO, Qdrant, Redis, FastAPI, Airflow, and a
deterministic OpenAI-compatible provider, and then exercises real authenticated
user flows.

The automated scenarios validate upload through Bronze, Silver, Gold, and
Qdrant; ordered ingestion and query SSE; streaming and non-streaming answers;
Redis cache hits; PostgreSQL query/retrieval logs; Parquet, chunk, and vector
lineage agreement; Redis-loss recovery through durable PostgreSQL snapshots;
durable pipeline and provider failures; and cross-tenant access denial.

The E2E overlay uses deterministic dense/sparse embeddings and a local provider
so mandatory CI requires no external model downloads or paid API credentials.
FastEmbed and the configured Gemini/Groq endpoints remain the default runtime
behavior outside the E2E environment. A GitHub Actions workflow runs the suite
for relevant pull requests and can also be triggered manually.

---

# Task 27 — Build the Frontend Control-Plane Experience

## Goal

Expose ingestion, document, query, and retrieval state through a truthful,
ChatGPT-style user experience backed by the completed APIs.

## Required Work

* Add authenticated project and document selection.
* Add document upload with immediate acceptance and ingestion-run tracking.
* Render backend ingestion stages, elapsed time, terminal success, and failures.
* Stream query stage events and answer tokens from `POST /rag/query/stream`.
* Use streaming `fetch` so the JWT remains in the authorization header.
* Reconnect ingestion streams with `Last-Event-ID` and fall back to the status
  endpoint when a stream cannot resume.
* Show retry actions and backend error messages without inventing progress.
* Add query history and optional retrieval-trace views for debugging.

### Acceptance Criteria

* Refreshing the page does not lose the durable ingestion state.
* Active stages animate, completed stages are marked, and elapsed time is local.
* Streamed tokens reconstruct the same final answer stored by the backend.
* Failed operations show a clear error and a safe retry path.
* Tenant and project boundaries are preserved in every frontend request.
* Frontend tests cover success, reconnect, empty, loading, and failure states.

## Implementation Status — Complete (2026-07-16)

Task 27 adds a greenfield Next.js App Router frontend under `frontend/` with
TypeScript, Tailwind CSS, TanStack Query, React Hook Form, Zod, and a focused
component system. It provides registration/login, responsive project
navigation, project creation, document upload with chunker selection, live
ingestion stage rendering, durable refresh recovery, failed-run retry, streamed
RAG chat, source inspection, query history, and ranked retrieval traces.

Authentication is exchanged through Next.js route handlers and stored in an
HttpOnly cookie. A same-origin proxy forwards JSON, multipart uploads, and SSE
streams to FastAPI without exposing the JWT to browser JavaScript. Ingestion
reconnection persists `Last-Event-ID`, replays available events, and falls back
to the durable run-status endpoint.

Supporting FastAPI endpoints list recent tenant-owned ingestion runs, retry
failed runs from their existing Bronze object, list project query history, and
return one query with chunk/document retrieval metadata. Frontend tests cover
loading, empty, success, backend validation failure, durable ingestion failure,
SSE fragmentation, terminal completion, and reconnect recovery. The production
Next.js image is part of Docker Compose and CI runs lint, tests, and builds.

---

# Task 28 — Production Readiness and Operations

## Goal

Harden and operate the completed control plane safely outside local development.

## Required Work

* Rotate any credentials that were ever pasted, shared, or committed.
* Generate unique production secrets for JWT, Airflow, Fernet, internal service
  authentication, PostgreSQL, MinIO, Redis, and provider access.
* Store secrets in the deployment platform's secret manager rather than `.env`.
* Configure TLS, trusted origins, network boundaries, and least-privilege service
  accounts for PostgreSQL, MinIO, Qdrant, Redis, and Airflow.
* Define PostgreSQL and object-storage backup and restore procedures.
* Add health checks, structured logs, metrics, traces, and alerts for ingestion
  failures, stuck runs, queue delay, query latency, and provider errors.
* Add rate limits, upload limits, retention policies, and data deletion workflows.
* Run concurrency, large-document, reconnect, retry, and recovery load tests.
* Add CI/CD gates for tests, migrations, container builds, and secret scanning.

### Acceptance Criteria

* A production deployment uses no development credentials or default passwords.
* Backup restoration and migration rollback are tested and documented.
* Operators can detect failed or stuck ingestion and trace a query end to end.
* Load-test targets and service-level objectives are defined and met.
* Deployment and rollback can be repeated from version-controlled automation.

## Implementation Status — Planned

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
21. Add authenticated real-time progress and query streaming.
22. Integrate completed control-plane branches into dev.
23. Wire and test the real Airflow data-plane commands.
24. Add full containerized end-to-end control-plane validation.
25. Build the frontend control-plane and streaming experience.
26. Complete production hardening, operations, and deployment validation.
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
* Real-time ingestion and answer progress

The final database supports both Data Engineering and AI Engineering use cases.
Tasks 24–28 complete the remaining integration, user experience, and operational
work required before describing the whole platform as production-ready.
