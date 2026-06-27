from fastapi import FastAPI
from app.api.documents import router as documents_router
from app.api.query import router as query_router

app = FastAPI(title="RAGForge API")

app.include_router(documents_router, prefix="/documents", tags=["documents"])
app.include_router(query_router, prefix="/rag", tags=["rag"])

@app.get("/health")
def health():
    return {"status": "ok"}