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

This starts PostgreSQL on `5432` and Qdrant on `6333`.

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

### 4. Create tables

```bash
cd backend
python create_tables.py
```

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
| POST | `/ingest/file` | Upload and index a file |
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

### Query

| Method | Endpoint | Description |
|---|---|---|
| POST | `/rag/query` | Text RAG query |
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
```

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
