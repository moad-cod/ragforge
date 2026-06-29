# RAGForge

A developer-friendly RAG SaaS platform with built-in evaluation. Upload documents, query them with an LLM, and measure the quality of every answer — automatically.

> **Core differentiator:** Most RAG platforms give you retrieval. RAGForge gives you retrieval *and* tells you how good it is.

---

## What it does

- Ingest documents from multiple sources (files, URLs, Google Drive)
- Chunk, embed, and index them into a vector database
- Answer questions using retrieved context + an LLM
- Automatically evaluate answer quality with RAGAS metrics
- Track performance over time in an evaluation dashboard

---

## Supported formats

| Source | Formats |
|---|---|
| File upload | PDF, DOCX, TXT, MD, XLSX, CSV, PPTX, HTML |
| URL scrape | Any public webpage |
| Google Drive | Google Docs, Sheets, Slides + any binary file stored in Drive |

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Python 3.12 |
| Frontend | Next.js 15 + TypeScript + Tailwind + shadcn/ui |
| Database | PostgreSQL |
| Vector DB | Qdrant |
| Embeddings | Sentence Transformers |
| LLM | Groq |
| Evaluation | RAGAS |
| Observability | Helicone |
| Background jobs | Celery + Redis |
| Deployment | Railway (backend) + Vercel (frontend) |

---

## Project structure

```
ragforge/
├── backend/
│   ├── app/
│   │   ├── api/                 # Route handlers
│   │   │   └── documents.py     # Upload endpoints
│   │   ├── services/
│   │   │   ├── parser.py        # Multi-format document parser
│   │   │   ├── chunker.py       # Chunking strategies (v1/v2/v3)
│   │   │   ├── embedder.py      # Embedding generation
│   │   │   └── retriever.py     # Qdrant storage + retrieval
│   │   ├── evaluation/          # RAGAS evaluation module
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── ragas_evaluator.py
│   │   │   └── metrics.py
│   │   ├── models/
│   │   └── schemas/
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── app/
│   ├── components/
│   └── lib/
├── docker-compose.yml
└── README.md
```

---

## Getting started

### Prerequisites

- Python 3.12
- Docker + Docker Compose
- A Groq API key (free at [console.groq.com](https://console.groq.com))

### 1. Clone the repo

```bash
git clone https://github.com/yourname/ragforge.git
cd ragforge
```

### 2. Start infrastructure

```bash
docker-compose up -d   # starts PostgreSQL + Qdrant
```

### 3. Set up the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
```

```env
# .env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ragforge
QDRANT_URL=http://localhost:6333
GROQ_API_KEY=your_groq_api_key
```

### 5. Run the backend

```bash
uvicorn app.main:app --reload
```

API docs available at `http://localhost:8000/docs`

---

## API endpoints

### Ingest

| Method | Endpoint | Description |
|---|---|---|
| POST | `/documents/upload/file` | Upload a local file |
| POST | `/documents/upload/url` | Scrape a public URL |
| POST | `/documents/upload/gdrive` | Import from Google Drive |

### Chunking versions

Pass `?version=v1` (default), `v2`, or `v3` to any upload endpoint:

| Version | Strategy |
|---|---|
| v1 | Paragraph-based |
| v2 | Proposition-based |
| v3 | Sentence-based |

### Example — upload a file

```bash
curl -X POST http://localhost:8000/documents/upload/file \
  -F "file=@report.pdf" \
  -F "version=v1"
```

```json
{
  "doc_id": "a1b2c3d4-...",
  "version": "v1",
  "source": "file",
  "name": "report.pdf",
  "chunks_indexed": 42,
  "sample_chunks": ["...", "...", "..."]
}
```

### Example — scrape a URL

```bash
curl -X POST http://localhost:8000/documents/upload/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://en.wikipedia.org/wiki/Retrieval-augmented_generation", "version": "v1"}'
```

### Example — Google Drive

```bash
curl -X POST http://localhost:8000/documents/upload/gdrive \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "your_drive_file_id",
    "access_token": "your_oauth_token",
    "version": "v1"
  }'
```

To get a test OAuth token, use the [Google OAuth Playground](https://developers.google.com/oauthplayground) with the Drive API `readonly` scope.

---

## Evaluation (coming in Phase 2)

RAGForge will automatically score every answer using RAGAS metrics:

| Metric | What it measures |
|---|---|
| Faithfulness | Is the answer grounded in the retrieved context? |
| Answer Relevance | Does the answer actually address the question? |
| Context Precision | Are the retrieved chunks relevant? |
| Hallucination Rate | How often does the system make things up? |

Results are stored per query and visualised in a dashboard so you can track quality trends over time and compare chunking/retrieval strategies against each other.

---

## Roadmap

- [x] Phase 1 — Multi-format document ingestion (PDF, DOCX, XLSX, PPTX, CSV, HTML, URL, Google Drive)
- [ ] Phase 2 — Query API + RAGAS evaluation + human feedback
- [ ] Phase 3 — Failure analysis + A/B testing + synthetic test generation
- [ ] Phase 4 — Usage-based pricing + self-hosting option + onboarding flow

---

## Cost estimate

| Stage | Monthly cost | Notes |
|---|---|---|
| MVP | $0 – $80 | Mostly free tiers |
| Early users | $100 – $400 | Qdrant + parsing dominate |
| Growing | $500 – $2,500+ | Scales with document volume |

---

## License

MIT