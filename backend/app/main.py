from fastapi import FastAPI
from app.api.ingest import router as ingest_router
from app.api.query import router as query_router

app = FastAPI(title="RAGForge API")

app.include_router(ingest_router, prefix="/ingest", tags=["ingest"])
app.include_router(query_router, prefix="/rag", tags=["rag"])

@app.get("/health")
def health():
    return {"status": "ok"}