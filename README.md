# RAGForge

A production-ready RAG (Retrieval-Augmented Generation) SaaS backend with strong evaluation capabilities, multi-tenant auth, and support for multiple LLM providers.

---

## Features

- **Multi-tenant** — each user owns their projects and documents, fully isolated
- **Multiple file types** — PDF, DOCX, XLSX, PPTX, CSV, HTML, Markdown, TXT
- **Multiple ingest sources** — file upload, URL scraping, Google Drive
- **Multiple LLM providers** — Gemini and Groq (OpenAI-compatible API)
- **Multiple chunking strategies** — paragraph, sentence, proposition
- **Vector search** — Qdrant with per-project and per-document filtering
- **JWT authentication** — secure, stateless, 7-day token expiry
- **Full CRUD** — users, projects, documents

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Python 3.12 |
| Database | PostgreSQL (asyncpg + SQLAlchemy async) |
| Vector DB | Qdrant |
| Embeddings | BAAI/bge-small-en-v1.5 (local, no API key) |
| LLM | Gemini 2.5 Flash / Groq Llama 3.3 70B |
| Auth | JWT (python-jose) + bcrypt |
| Parsing | PyMuPDF, python-docx, openpyxl, python-pptx, BeautifulSoup |

---

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── auth.py         # register, login, me
│   │   ├── projects.py     # project CRUD
│   │   ├── documents.py    # document CRUD
│   │   ├── ingest.py       # file / url / gdrive upload
│   │   └── query.py        # RAG query endpoint
│   ├── core/
│   │   ├── auth.py         # JWT dependency
│   │   ├── config.py       # settings from .env
│   │   └── db.py           # async SQLAlchemy engine
│   ├── models/
│   │   └── tables.py       # User, Project, Document
│   ├── services/
│   │   ├── parser.py       # file + url + gdrive parsers
│   │   ├── embedder.py     # sentence-transformers
│   │   ├── indexer.py      # Qdrant upsert + delete
│   │   ├── retriever.py    # Qdrant search
│   │   └── chunkers/
│   │       ├── paragraph.py
│   │       ├── sentence.py
│   │       └── proposition.py
│   └── main.py
├── create_tables.py
├── requirements.txt
└── .env
```

---

## Setup

### 1. Prerequisites

- Python 3.12+
- PostgreSQL running locally
- Qdrant running locally (`docker run -p 6333:6333 qdrant/qdrant`)

### 2. Clone and install

```bash
git clone https://github.com/yourname/ragforge.git
cd ragforge/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment variables

Create a `.env` file:

```dotenv
DATABASE_URL=postgresql+asyncpg://ragforge:ragforge@localhost:5432/ragforge
SECRET_KEY=your-random-secret-key-here

QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
```

Generate a secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Create database

```bash
psql -U postgres -c "CREATE USER ragforge WITH PASSWORD 'ragforge';"
psql -U postgres -c "CREATE DATABASE ragforge OWNER ragforge;"
```

### 5. Create tables

```bash
python create_tables.py
```

### 6. Run

```bash
uvicorn app.main:app --reload
```

API docs: `http://localhost:8000/docs`

---

## API Reference

### Auth

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Get JWT token |
| GET | `/auth/me` | Get current user |
| PATCH | `/auth/me` | Update email or password |
| DELETE | `/auth/me` | Delete account + all data |

### Projects

| Method | Endpoint | Description |
|---|---|---|
| POST | `/projects/` | Create project |
| GET | `/projects/` | List projects |
| GET | `/projects/{id}` | Get project |
| PATCH | `/projects/{id}` | Rename project |
| DELETE | `/projects/{id}` | Delete project + documents + Qdrant collection |

### Documents

| Method | Endpoint | Description |
|---|---|---|
| GET | `/documents/?project_id=` | List documents |
| GET | `/documents/{id}` | Get document |
| DELETE | `/documents/{id}` | Delete document + Qdrant chunks |

### Ingest

| Method | Endpoint | Description |
|---|---|---|
| POST | `/ingest/file` | Upload file (multipart/form-data) |
| POST | `/ingest/url` | Scrape a public URL |
| POST | `/ingest/gdrive` | Import from Google Drive |

**Ingest file params:**
```
file        — the file (PDF, DOCX, XLSX, PPTX, CSV, HTML, MD, TXT)
project_id  — which project to index into
chunker     — paragraph | sentence | proposition (default: paragraph)
```

### RAG Query

| Method | Endpoint | Description |
|---|---|---|
| POST | `/rag/query` | Query documents with LLM |

**Request body:**
```json
{
  "question": "what is in the documents?",
  "project_id": "your-project-id",
  "provider": "gemini",
  "model": null,
  "document_id": null
}
```

---

## Quick Start (curl)

```bash
# Register
curl -s -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "secret123"}'

# Login
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=you@example.com&password=secret123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Create project
PROJECT_ID=$(curl -s -X POST "http://localhost:8000/projects/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "my docs"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['project_id'])")

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
  -d "{\"question\": \"what is in the documents?\", \"project_id\": \"$PROJECT_ID\", \"provider\": \"gemini\"}"
```

---

## Data Isolation

Every Qdrant point is stored with `project_id` and `document_id` in its payload. All queries filter by `project_id` and verify ownership via JWT before executing — users can never access each other's data.

```
User → Projects → Documents → Qdrant points
         └── Qdrant collection (auto-created, auto-deleted)
```

---

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

---

## Chunking Strategies

| Strategy | Description | Best for |
|---|---|---|
| `paragraph` | Split on double newlines | General documents |
| `sentence` | Split on sentence boundaries | Dense text |
| `proposition` | Semantic proposition extraction | High accuracy RAG |

---

## LLM Providers

| Provider | Default Model | Notes |
|---|---|---|
| `gemini` | gemini-2.5-flash | Via Google AI Studio |
| `groq` | llama-3.3-70b-versatile | Fast inference |

Override the model per request with the `model` field.

---

## Roadmap

- [ ] Evaluation module (RAGAS metrics)
- [ ] A/B testing between retrieval strategies
- [ ] Evaluation dashboard
- [ ] Synthetic test question generation
- [ ] Failure analysis
- [ ] Stripe billing
- [ ] Frontend (Next.js)