Core Entity:

***The database answers:
Who uploaded the document?
Which project does it belong to?
Which version is active?
Where is the raw file in Bronze?
Where are cleaned chunks in Silver?
Where is embedded metadata in Gold?
Did ingestion succeed or fail?
Which chunks were indexed in Qdrant?
Which chunks were retrieved for a user query?
Was the answer cached?

Core entities

1. projects

Purpose: groups documents, queries, Qdrant filtering, and user access.

projects
- id UUID primary key
- organization_id UUID nullable / not null depending on multi-tenancy
- name text not null
- qdrant_collection text unique not null
- created_by UUID
- created_at timestamp
- updated_at timestamp
- deleted_at timestamp nullable

Important: not generate Qdrant collection names from project names. Use immutable IDs


2. documents

This is the logical document.

A document can have many versions. For example, if the user uploads report.pdf, then later re-uploads an updated report.pdf, it is still the same logical document but with a new version.

documents
- id UUID primary key
- project_id UUID not null
- current_version_id UUID nullable
- source_type text
- filename text
- mime_type text
- extension text
- status text
- created_by UUID
- created_at timestamp
- updated_at timestamp
- deleted_at timestamp nullable

statuses:
uploaded
landed
processing
chunked
embedded
indexed
failed
deleted

Design meaning:
documents = the business object
document_versions = the physical uploaded/processed version

3. document_versions

Every upload or re-ingestion creates a new document_version_id. This prevents silent overwrites and allows you to rebuild, compare, audit, and evaluate old versions.

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
- status text
- error_message text nullable
- created_at timestamp

constraints:

unique(document_id, version_number)
unique(document_id, content_hash)
foreign key document_id references documents(id)

This table connects PostgreSQL to MinIO:

bronze_path = raw file location
silver_path = cleaned chunks parquet location
gold_path   = embedded metadata parquet location

4. ingestion_runs

This table tracks every pipeline execution.

A document version may have one or more ingestion runs. For example, if one run fails and you retry it, you can keep the history.

ingestion_runs
- id UUID primary key
- project_id UUID not null
- document_id UUID not null
- document_version_id UUID not null
- status text
- started_at timestamp nullable
- finished_at timestamp nullable
- error_message text nullable
- airflow_dag_run_id text nullable
- created_by UUID
- created_at timestamp

statuses:

landed
queued
running
silver_completed
gold_completed
indexed
failed
cancelled

This table is important because upload should return immediately:
The actual parsing, chunking, embedding, and indexing happen later through Airflow/Spark jobs.

5. chunks

This table stores chunk metadata, not the embedding vector.

The vector goes to Qdrant. The full processed data also exists in Silver/Gold Parquet. PostgreSQL keeps the searchable metadata and IDs.

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
- created_at timestamp

constraints:
unique(document_version_id, chunk_index)
unique(document_version_id, content_hash)
foreign key document_id references documents(id)
foreign key document_version_id references document_versions(id)
foreign key ingestion_run_id references ingestion_runs(id)

Qdrant point ID:
{document_version_id}:{chunk_index}

This makes Qdrant rebuildable and idempotent.

6. embedding_runs

This table tracks embedding generation.

It helps you know which embedding model was used, how many chunks were embedded, and whether the process failed.

embedding_runs
- id UUID primary key
- project_id UUID not null
- document_version_id UUID not null
- embedding_model text not null
- status text
- total_chunks int default 0
- embedded_chunks int default 0
- started_at timestamp nullable
- finished_at timestamp nullable
- error_message text nullable
- created_at timestamp

constraint:
unique(document_version_id, embedding_model)

This lets you compare different embedding models later.

Example:
same document_version_id
  → embedding model A
  → embedding model B

Good for evaluation and experimentation.

7. query_logs

This table tracks user questions.

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
- created_at timestamp

I would add these fields from your agentic RAG response:

route
relevance_score
groundedness_score

Because your /rag/agent-query endpoint returns them, so they should be stored for debugging and evaluation.


8. retrieval_logs

This table tracks which chunks were retrieved for each query.

This is very useful for RAG evaluation.

retrieval_logs
- id UUID primary key
- query_log_id UUID not null
- chunk_id UUID nullable
- qdrant_score float nullable
- rerank_score float nullable
- rank int
- retrieval_strategy text
- used_in_answer boolean default false
- created_at timestamp

Relationship:
query_logs 1 → many retrieval_logs
chunks 1 → many retrieval_logs

This allows you to answer:
Which chunks were retrieved?
Which chunks were used in the final answer?
What was the Qdrant score?
What was the rerank score?
Was retrieval good or weak?

