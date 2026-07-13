# RAGForge

RAGForge is a FastAPI SaaS backend for multi-tenant Retrieval-Augmented Generation. It supports authenticated users, projects, document ingestion, professional chunking modes, Qdrant vector search, and OpenAI-compatible LLM providers.

## Features

- Multi-tenant JWT authentication.
- Project and document CRUD with ownership checks.
- File, URL, Google Drive, and multimodal PDF ingestion.
- SaaS-style chunker registry exposed through `GET /chunkers`.
- Text chunkers: fixed-size, paragraph, sentence, semantic, hierarchical, late chunking, proposition.
- Multimodal PDF page ingestion with Qdrant multivectors and Cloudflare R2 images.
- Dense+sparse Qdrant indexing and hybrid retrieval.
- Optional cross-encoder reranking.
- Gemini and Groq query providers.
- Local BGE embeddings with lazy model loading.
- Development reset and smoke-test scripts.
- Alembic-managed PostgreSQL control-plane schema and repository layer.
- Asynchronous file landing in MinIO Bronze with durable ingestion-run status.
- Durable query and ranked retrieval observability with best-effort Redis caching.
- Authenticated ingestion progress SSE and token-by-token RAG query streaming.

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI |
| Database | PostgreSQL, SQLAlchemy async, asyncpg |
| Vector DB | Qdrant |
| Dense embeddings | `BAAI/bge-small-en-v1.5` via sentence-transformers |
| Sparse retrieval | FastEmbed BM25 |
| Reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| LLM providers | Gemini OpenAI-compatible API, Groq OpenAI-compatible API |
| Multimodal | ColQwen2 / ColPali-style page embeddings |
| Object storage | Cloudflare R2 |
| Parsing | PyMuPDF, python-docx, openpyxl, python-pptx, BeautifulSoup |
| Auth | JWT with `python-jose`, bcrypt |

## Project Structure

```text
backend/
  app/
    api/
      auth.py          # register, login, me
      chunkers.py      # GET /chunkers metadata
      documents.py     # document list/get/delete
      ingest.py        # file/url/gdrive/multimodal ingestion
      projects.py      # project CRUD
      query.py         # text and multimodal RAG query
    core/
      auth.py          # JWT dependency
      config.py        # .env settings
      db.py            # async SQLAlchemy session
    models/
      tables.py        # User, Project, Document
    services/
      parser.py        # file, URL, Drive parsers
      embedder.py      # lazy BGE embedder
      indexer.py       # Qdrant upsert/delete
      retriever.py     # retrieval entry point
      retrieval/       # dense/sparse/hybrid/rerank
      chunkers/        # chunking implementations + registry
  create_tables.py     # create missing tables
  reset_dev_db.py      # destructive local reset
  tests/               # registry/API/evaluation scripts
docker-compose.yml     # Postgres + Qdrant
test_chunkers.sh       # end-to-end smoke test
PROJECT_MAP.md         # architecture and design map
```

## Setup

### 1. Start infrastructure

```bash
docker compose up -d
```

This starts PostgreSQL, Qdrant, MinIO, Redis, and the FastAPI development app.

### 2. Install backend dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment

Create `backend/.env` from the root `.env.example` values:

```dotenv
DATABASE_URL=postgresql+asyncpg://ragforge:ragforge@localhost:5432/ragforge
SECRET_KEY=replace-with-a-random-secret

QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

REDIS_URL=redis://localhost:6379/0
QUERY_CACHE_TTL_SECONDS=300
EVENT_STREAM_MAXLEN=512
EVENT_STREAM_TTL_SECONDS=3600
SSE_HEARTBEAT_SECONDS=15
SSE_POLL_SECONDS=1

GEMINI_API_KEY=
GROQ_API_KEY=

R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_PUBLIC_URL=

DEBUG_RETURN_CONTEXT=false
MAX_UPLOAD_BYTES=26214400
MAX_MULTIMODAL_PAGES=50
```

Generate a secret key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Apply database migrations

```bash
cd backend
alembic upgrade head
```

`create_tables.py` remains available only as a development compatibility helper. For a database previously created directly from SQLAlchemy metadata, use a fresh development reset or verify the schema before stamping the Alembic revision.

Create one complete, repeatable development dataset and validate the migrated
schema:

```bash
python seed_control_plane.py --namespace development
python validate_control_plane.py
```

The seed command is idempotent for each namespace. Use a different namespace
when you want an additional independent example project.

For a fresh destructive local reset of PostgreSQL tables and Qdrant collections:

```bash
cd backend
python reset_dev_db.py
```

### 5. Run the API

```bash
cd backend
uvicorn app.main:app --reload
```

API docs: `http://localhost:8000/docs`

### 6. Start Airflow 3.3 and Spark (optional)

The `batch` profile runs the Airflow 3 API server/new UI, scheduler, DAG
processor, triggerer, metadata database, and Spark. In the root `.env`, set:

```dotenv
AIRFLOW_API_URL=http://airflow-apiserver:8080
AIRFLOW_USERNAME=admin
AIRFLOW_PASSWORD=admin
AIRFLOW_API_JWT_SECRET=replace-with-a-random-airflow-jwt-secret
PIPELINE_SERVICE_TOKEN=replace-with-a-random-internal-token
```

Then start the profile:

```bash
docker compose --profile batch up -d
```

Open the Airflow UI at `http://localhost:8080` and sign in with the configured
Airflow username and password. Check initialization and scheduler health with:

```bash
docker compose --profile batch ps
docker compose logs airflow-init airflow-apiserver airflow-scheduler airflow-dag-processor
```

`airflow-init` exiting successfully is expected. Existing Airflow 2 development
metadata may need a fresh `airflow_postgres_data` volume if its major-version
migration is not usable; this does not affect the main RAGForge PostgreSQL
volume.

## API Reference

### Health

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | API health check |

### Auth

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Get JWT token |
| GET | `/auth/me` | Get current user |
| PATCH | `/auth/me` | Update email or password |
| DELETE | `/auth/me` | Delete account and owned data |

### Projects

| Method | Endpoint | Description |
|---|---|---|
| POST | `/projects/` | Create project |
| GET | `/projects/` | List projects |
| GET | `/projects/{project_id}` | Get project |
| PATCH | `/projects/{project_id}` | Rename project |
| DELETE | `/projects/{project_id}` | Delete project, documents, and Qdrant collections |

### Documents

| Method | Endpoint | Description |
|---|---|---|
| GET | `/documents/?project_id=` | List project documents |
| GET | `/documents/{document_id}` | Get document |
| DELETE | `/documents/{document_id}` | Delete document and vector/image artifacts |

### Chunkers

| Method | Endpoint | Description |
|---|---|---|
| GET | `/chunkers` | List public chunking modes and product metadata |

### Ingest

| Method | Endpoint | Description |
|---|---|---|
| POST | `/ingest/file` | Land a file in Bronze and return an ingestion run (HTTP 202) |
| GET | `/ingest/runs/{ingestion_run_id}` | Read durable Bronze/Silver/Gold/Qdrant progress |
| GET | `/ingest/runs/{ingestion_run_id}/events` | Stream durable progress snapshots and replayable SSE events |
| POST | `/ingest/url` | Scrape and index a public URL |
| POST | `/ingest/gdrive` | Import and index a Google Drive file |
| POST | `/ingest/multimodal` | Render, embed, upload, and index PDF pages |

`/ingest/file` multipart fields:

```text
file       PDF, DOCX, XLSX, PPTX, CSV, HTML, MD, TXT
project_id target project ID
chunker    fixed_size | paragraph | sentence | semantic | hierarchical | late_chunking | proposition
```

`multimodal` is listed by `GET /chunkers`, but text file ingestion rejects it because it uses `/ingest/multimodal`.

`POST /ingest/file` returns immediately after durable landing:

```json
{
  "document_id": "uuid",
  "document_version_id": "uuid",
  "ingestion_run_id": "uuid",
  "status": "landed"
}
```

Set `AIRFLOW_API_URL=http://airflow-apiserver:8080` and `PIPELINE_SERVICE_TOKEN` to enqueue landed runs automatically. FastAPI obtains an Airflow JWT and uses the public Airflow 3 `/api/v2` endpoint. The DAG also requires the three data-plane command variables documented in `.env.example`; missing commands fail the run instead of marking incomplete processing as successful.

### Query

| Method | Endpoint | Description |
|---|---|---|
| POST | `/rag/query` | Text RAG query |
| POST | `/rag/query/stream` | Stream RAG stages and answer tokens over SSE |
| POST | `/rag/multimodal-query` | Page-image multimodal query |

Text query body:

```json
{
  "question": "What is in the documents?",
  "project_id": "project-id",
  "provider": "gemini",
  "model": null,
  "document_id": null,
  "use_parent_context": false,
  "include_context": false
}
```

## Chunking Modes

The registry in `backend/app/services/chunkers/registry.py` is the single source of truth. It is lightweight and does not import heavy ML models until a chunker is actually called.

| ID | Product Name | Tier | Status | Best For |
|---|---|---|---|---|
| `fixed_size` | Starter Chunking | Base | Stable | Testing and predictable chunks |
| `paragraph` | Base Chunking | Base | Stable | Fast general-purpose ingestion |
| `sentence` | Precision Chunking | Pro | Stable | Dense text and long paragraphs |
| `semantic` | Semantic Chunking | Pro | Beta | Meaning-aware retrieval |
| `hierarchical` | Structured Chunking | Business | Beta | Headings, sections, manuals |
| `late_chunking` | Late Interaction Chunking | Ultimate | Beta | Premium retrieval quality |
| `proposition` | Ultimate Chunking | Ultimate | Beta | Highest-accuracy semantic RAG |
| `multimodal` | Multimodal Chunking | Ultimate | Experimental | Visual PDFs and image-heavy documents |

## Quick Start

```bash
# Register
curl -s -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "secret123"}'

# Login
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=you@example.com&password=secret123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[\"access_token\"])")

# Create project
PROJECT_ID=$(curl -s -X POST "http://localhost:8000/projects/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "my docs"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[\"project_id\"])")

# List chunking modes
curl -s "http://localhost:8000/chunkers" | python3 -m json.tool

# Upload file
curl -X POST "http://localhost:8000/ingest/file" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/file.pdf" \
  -F "project_id=$PROJECT_ID" \
  -F "chunker=paragraph"

# Query
curl -s -X POST "http://localhost:8000/rag/query" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"What is in the documents?\",\"project_id\":\"$PROJECT_ID\",\"provider\":\"gemini\"}"

# Stream ingestion progress (use the ingestion_run_id returned by /ingest/file)
curl -N "http://localhost:8000/ingest/runs/$INGESTION_RUN_ID/events" \
  -H "Authorization: Bearer $TOKEN"

# Stream query stages and generated tokens
curl -N -X POST "http://localhost:8000/rag/query/stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"What is in the documents?\",\"project_id\":\"$PROJECT_ID\",\"provider\":\"gemini\"}"
```

Browser clients should use streaming `fetch` so the JWT remains in the
`Authorization` header. Ingestion reconnects may send `Last-Event-ID`; Redis
replays retained events when available, otherwise the first PostgreSQL
snapshot remains authoritative.

## Data Isolation

Every project belongs to a user. Every document belongs to a project. Qdrant points include `project_id` and `document_id` payloads, and query paths verify project ownership before retrieval.

```text
User -> Projects -> Documents -> Qdrant points
```

Project Qdrant collections are UUID-based, not display-name-based, to avoid cross-tenant collisions.

## Supported File Types

| Extension | Parser |
|---|---|
| `.pdf` | PyMuPDF |
| `.docx` | python-docx |
| `.xlsx` | openpyxl |
| `.pptx` | python-pptx |
| `.csv` | csv stdlib |
| `.html` / `.htm` | BeautifulSoup |
| `.md` / `.txt` | plain text |

## Testing and Development

Run the registry/unit-style tests:

```bash
cd backend
PYTHONPATH=. python -m unittest tests.test_chunker_registry tests.test_chunkers_api -v
```

Run the Tasks 21–22 PostgreSQL integration suite:

```bash
cd backend
RUN_DATABASE_TESTS=1 python -m unittest tests.test_control_plane_database -v
```

The suite derives an isolated database named `ragforge_test` from
`DATABASE_URL`, performs a full Alembic upgrade/rollback/upgrade cycle, tests
the seed graph and database constraints, then rolls the test schema back. Set
`TEST_DATABASE_URL` explicitly when a different `_test` database is required.

Run the Task 23 streaming tests and optional live Redis replay test:

```bash
cd backend
python -m unittest tests.test_realtime_streaming -v
RUN_REDIS_TESTS=1 python -m unittest tests.test_realtime_streaming.RedisEventIntegrationTests -v
```

Run the full smoke test from the project root:

```bash
./test_chunkers.sh
```

The smoke test uses `Rapport_de_stage_bac+3.pdf`, checks `/chunkers`, ingests the document with all text chunkers, validates invalid chunkers, queries, and cleans up the created project.

Useful toggles:

```bash
RUN_LLM_TESTS=0 ./test_chunkers.sh
RUN_URL_TEST=1 RUN_GDRIVE_TEST=1 RUN_MULTIMODAL_TEST=1 ./test_chunkers.sh
```

## More Detail

See `PROJECT_MAP.md` for the architecture map, data flow, module responsibilities, and current design notes.
