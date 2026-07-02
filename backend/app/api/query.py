from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Literal
from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.tables import Project
from app.services.embedder import embed_query
from app.services.retriever import search
from app.core.config import settings
from app.services.chunkers.multimodal import embed_query_tokens  # ← fixed typo
from openai import OpenAI
from qdrant_client import QdrantClient                           # ← added
from qdrant_client.models import Filter, FieldCondition, MatchValue  # ← added

router = APIRouter()

qdrant = QdrantClient(                                           # ← added
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY or None,
)

LLM_CONFIGS = {
    "gemini": {
        "api_key": lambda: settings.GEMINI_API_KEY,
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.5-flash",
    },
    "groq": {
        "api_key": lambda: settings.GROQ_API_KEY,
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
    },
}

def get_llm_client(provider: str) -> tuple[OpenAI, str]:
    config = LLM_CONFIGS[provider]
    return OpenAI(api_key=config["api_key"](), base_url=config["base_url"]), config["default_model"]


class QueryRequest(BaseModel):
    question: str
    project_id: str
    provider: Literal["gemini", "groq"] = "gemini"
    model: str | None = None
    document_id: str | None = None
    use_parent_context: bool = False


@router.post("/query")
async def query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Project).where(
            Project.id == request.project_id,
            Project.user_id == user["user_id"],
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(403, "Project not found or access denied")

    query_embedding = embed_query(request.question)

    contexts = search(
        embedding=query_embedding,
        project_id=request.project_id,
        collection=project.collection,
        document_id=request.document_id,
        use_parent_context=request.use_parent_context,
    )

    if not contexts:
        return {
            "question": request.question,
            "project_id": request.project_id,
            "collection": project.collection,
            "answer": "No documents found for this project.",
            "retrieved_chunks": [],
        }

    context_text = "\n\n---\n\n".join(contexts)
    prompt = f"""Answer the question using ONLY the context below.
If the answer isn't in the context, say "I don't know based on the provided documents."

Context:
{context_text}

Question: {request.question}"""

    client, default_model = get_llm_client(request.provider)
    model = (request.model or "").strip() or default_model

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )

    return {
        "question": request.question,
        "project_id": request.project_id,
        "collection": project.collection,
        "provider": request.provider,
        "model": model,
        "use_parent_context": request.use_parent_context,
        "answer": response.choices[0].message.content,
        "retrieved_chunks": contexts,
    }


@router.post("/multimodal-query")
async def multimodal_query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Project).where(
            Project.id == request.project_id,
            Project.user_id == user["user_id"],
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(403, "Project not found or access denied")

    query_vectors = embed_query_tokens(request.question)
    collection = f"{project.collection}_multimodal"

    results = qdrant.query_points(
        collection_name=collection,
        query=query_vectors,
        query_filter=Filter(must=[
            FieldCondition(key="project_id", match=MatchValue(value=request.project_id))
        ]),
        limit=3,
    )

    if not results.points:
        return {"answer": "No pages found.", "pages": []}

    page_urls = [r.payload["page_image_url"] for r in results.points]

    messages = [
        {"type": "text", "text": f"Answer based strictly on the document pages below:\n{request.question}"},
        *[{"type": "image_url", "image_url": {"url": url}} for url in page_urls]
    ]

    client, _ = get_llm_client("gemini")
    response = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=[{"role": "user", "content": messages}],
        max_tokens=2048,
    )

    return {
        "question": request.question,
        "project_id": request.project_id,
        "answer": response.choices[0].message.content,
        "pages_used": [
            {"page_num": r.payload["page_num"], "image_url": r.payload["page_image_url"]}
            for r in results.points
        ],
    }