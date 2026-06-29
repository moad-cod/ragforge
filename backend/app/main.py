from fastapi import FastAPI
from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.ingest import router as ingest_router
from app.api.query import router as query_router

app = FastAPI(title="RAGForge API")

app.include_router(auth_router,     prefix="/auth",     tags=["auth"])
app.include_router(projects_router, prefix="/projects", tags=["projects"])
app.include_router(ingest_router,   prefix="/ingest",   tags=["ingest"])
app.include_router(query_router,    prefix="/rag",      tags=["rag"])