from fastapi import FastAPI
from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.ingest import router as ingest_router
from app.api.query import router as query_router
from app.api.documents import router as documents_router
from app.api.chunkers import router as chunkers_router
from app.api.organizations import router as organizations_router
from app.api.internal_pipeline import router as internal_pipeline_router

app = FastAPI(
    title="RAGForge API",
    swagger_ui_parameters={"persistAuthorization": True},
)

app.include_router(auth_router,      prefix="/auth",      tags=["auth"])
app.include_router(projects_router,  prefix="/projects",  tags=["projects"])
app.include_router(ingest_router,    prefix="/ingest",    tags=["ingest"])
app.include_router(query_router,     prefix="/rag",       tags=["rag"])
app.include_router(documents_router, prefix="/documents", tags=["documents"])
app.include_router(chunkers_router,  prefix="/chunkers",  tags=["chunkers"])
app.include_router(organizations_router, prefix="/organizations", tags=["organizations"])
app.include_router(
    internal_pipeline_router,
    prefix="/internal/pipeline",
    tags=["internal-pipeline"],
)

@app.get("/health")
def health():
    return {"status": "ok"}
