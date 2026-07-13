import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any, Literal
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from openai import OpenAI
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.db import AsyncSessionLocal, get_db
from app.models.tables import Document, Project
from app.repositories import query_logs as query_log_repository
from app.repositories import retrieval_logs as retrieval_log_repository
from app.services.embedder import embed_query
from app.services.query_cache import cache_key, get_cached_query, set_cached_query
from app.services.query_observability import normalized_question_hash, retrieval_log_values
from app.services.event_stream import StreamEvent, format_sse, heartbeat_sse, utc_timestamp
from app.services.retrieval.types import RetrievalHit
from app.services.retriever import search

router = APIRouter()

qdrant = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY or None,
    check_compatibility=False,
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
    try:
        settings.require_llm_provider(provider)
    except ValueError as exc:
        raise HTTPException(503, str(exc))
    config = LLM_CONFIGS[provider]
    return OpenAI(api_key=config["api_key"](), base_url=config["base_url"]), config["default_model"]


def resolve_model(provider: str, requested_model: str | None) -> str:
    return (requested_model or "").strip() or LLM_CONFIGS[provider]["default_model"]


class QueryRequest(BaseModel):
    question: str
    project_id: str
    provider: Literal["gemini", "groq"] = "gemini"
    model: str | None = None
    document_id: str | None = None
    use_parent_context: bool = False
    include_context: bool = False


QueryEventEmitter = Callable[[str, dict[str, Any]], Awaitable[None]]
_query_stream_tasks: set[asyncio.Task] = set()


async def _authorize_query(
    request: QueryRequest,
    db: AsyncSession,
    user_id: str,
):
    result = await db.execute(
        select(Project).where(
            Project.id == request.project_id,
            Project.created_by == user_id,
            Project.deleted_at.is_(None),
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(403, "Project not found or access denied")

    if request.document_id:
        doc_result = await db.execute(
            select(Document).where(
                Document.id == request.document_id,
                Document.project_id == request.project_id,
                Document.deleted_at.is_(None),
            )
        )
        if not doc_result.scalar_one_or_none():
            raise HTTPException(404, "Document not found in this project")
    return project


async def _notify(
    emit: QueryEventEmitter | None,
    event: str,
    **data: Any,
) -> None:
    if emit is not None:
        await emit(event, data)


def _next_stream_chunk(iterator):
    try:
        return next(iterator)
    except StopIteration:
        return None


def _response_payload(
    request: QueryRequest,
    project,
    *,
    query_log_id: str,
    model: str,
    cache_hit: bool,
    answer: str,
    contexts: list[str],
) -> dict[str, Any]:
    return {
        "query_log_id": query_log_id,
        "question": request.question,
        "project_id": request.project_id,
        "collection": project.collection,
        "provider": request.provider,
        "model": model,
        "use_parent_context": request.use_parent_context,
        "cache_hit": cache_hit,
        "answer": answer,
        **(
            {"retrieved_chunks": contexts}
            if request.include_context or settings.DEBUG_RETURN_CONTEXT
            else {}
        ),
    }


async def _execute_query(
    request: QueryRequest,
    db: AsyncSession,
    user_id: str,
    *,
    emit: QueryEventEmitter | None = None,
    stream_tokens: bool = False,
    route: str = "rag",
):
    started_at = time.perf_counter()
    await _notify(emit, "query.received", project_id=request.project_id)
    project = await _authorize_query(request, db, user_id)

    question_hash = normalized_question_hash(request.question)
    model = resolve_model(request.provider, request.model)
    response_cache_key = cache_key(
        project_id=request.project_id,
        normalized_question_hash=question_hash,
        provider=request.provider,
        model=model,
        document_id=request.document_id,
        use_parent_context=request.use_parent_context,
    )
    cached = await get_cached_query(response_cache_key)
    try:
        cached_hits = [RetrievalHit.from_cache_dict(value) for value in cached["hits"]] if cached else []
        cached_answer = cached["answer"] if cached and isinstance(cached["answer"], str) else None
        if cached and cached_answer is None:
            raise ValueError("Cached answer is not a string")
    except (KeyError, TypeError, ValueError):
        cached = None
        cached_hits = []
        cached_answer = None

    query_log = await query_log_repository.create_query_log(
        db,
        project_id=request.project_id,
        user_id=user_id,
        question=request.question,
        normalized_question_hash=question_hash,
        provider=request.provider,
        model=model,
        cache_hit=bool(cached),
        route=route,
    )
    finalized = False

    async def finalize(cache_hit: bool, answer: str | None) -> int:
        nonlocal finalized
        latency_ms = max(0, round((time.perf_counter() - started_at) * 1000))
        await query_log_repository.finish_query_log(
            db,
            query_log,
            latency_ms=latency_ms,
            cache_hit=cache_hit,
            route=route,
            answer=answer,
        )
        await db.commit()
        finalized = True
        return latency_ms

    try:
        if cached and cached_answer is not None:
            for hit in cached_hits:
                hit.used_in_answer = True
            await retrieval_log_repository.bulk_insert_retrieval_logs(
                db,
                retrieval_log_values(query_log.id, cached_hits, from_cache=True),
            )
            await _notify(emit, "query.token", text=cached_answer)
            latency_ms = await finalize(cache_hit=True, answer=cached_answer)
            contexts = [hit.text for hit in cached_hits]
            response_payload = _response_payload(
                request,
                project,
                query_log_id=query_log.id,
                model=model,
                cache_hit=True,
                answer=cached_answer,
                contexts=contexts,
            )
            await _notify(
                emit,
                "query.completed",
                query_log_id=query_log.id,
                provider=request.provider,
                model=model,
                latency_ms=latency_ms,
                cache_hit=True,
                **(
                    {"retrieved_chunks": contexts}
                    if request.include_context or settings.DEBUG_RETURN_CONTEXT
                    else {}
                ),
            )
            return response_payload

        await _notify(emit, "query.embedding")
        query_embedding = await asyncio.to_thread(embed_query, request.question)
        await _notify(emit, "query.retrieving")
        hits = await asyncio.to_thread(
            search,
            embedding=query_embedding,
            project_id=request.project_id,
            collection=project.collection,
            query_text=request.question,
            document_id=request.document_id,
            use_parent_context=request.use_parent_context,
        )
        await _notify(emit, "query.reranking", retrieved_chunks=len(hits))

        retrieval_logs = await retrieval_log_repository.bulk_insert_retrieval_logs(
            db,
            retrieval_log_values(query_log.id, hits),
        )

        if not hits:
            answer = "No documents found for this project."
            await _notify(emit, "query.token", text=answer)
            latency_ms = await finalize(cache_hit=False, answer=answer)
            response_payload = _response_payload(
                request,
                project,
                query_log_id=query_log.id,
                model=model,
                cache_hit=False,
                answer=answer,
                contexts=[],
            )
            await _notify(
                emit,
                "query.completed",
                query_log_id=query_log.id,
                provider=request.provider,
                model=model,
                latency_ms=latency_ms,
                cache_hit=False,
                **(
                    {"retrieved_chunks": []}
                    if request.include_context or settings.DEBUG_RETURN_CONTEXT
                    else {}
                ),
            )
            return response_payload

        contexts = [hit.text for hit in hits]
        context_text = "\n\n---\n\n".join(contexts)
        prompt = f"""Answer the question using ONLY the context below.
If the answer isn't in the context, say "I don't know based on the provided documents."

Context:
{context_text}

Question: {request.question}"""

        client, _default_model = get_llm_client(request.provider)
        await _notify(emit, "query.generating")
        if stream_tokens:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
                stream=True,
            )
            fragments: list[str] = []
            iterator = iter(response)
            while True:
                chunk = await asyncio.to_thread(_next_stream_chunk, iterator)
                if chunk is None:
                    break
                fragment = chunk.choices[0].delta.content or ""
                if fragment:
                    fragments.append(fragment)
                    await _notify(emit, "query.token", text=fragment)
            answer = "".join(fragments)
        else:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
            )
            answer = response.choices[0].message.content or ""

        for hit in hits:
            hit.used_in_answer = True
        await retrieval_log_repository.mark_retrieval_logs_used(db, retrieval_logs)
        latency_ms = await finalize(cache_hit=False, answer=answer)
        await set_cached_query(
            response_cache_key,
            {
                "answer": answer,
                "hits": [hit.to_cache_dict() for hit in hits],
            },
        )

        response_payload = _response_payload(
            request,
            project,
            query_log_id=query_log.id,
            model=model,
            cache_hit=False,
            answer=answer,
            contexts=contexts,
        )
        await _notify(
            emit,
            "query.completed",
            query_log_id=query_log.id,
            provider=request.provider,
            model=model,
            latency_ms=latency_ms,
            cache_hit=False,
            **(
                {"retrieved_chunks": contexts}
                if request.include_context or settings.DEBUG_RETURN_CONTEXT
                else {}
            ),
        )
        return response_payload
    except Exception as exc:
        if not finalized:
            try:
                await finalize(cache_hit=False, answer=None)
            except Exception:
                await db.rollback()
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        await _notify(
            emit,
            "query.failed",
            query_log_id=getattr(query_log, "id", None),
            error=str(detail) or "Query failed",
        )
        raise


@router.post("/query")
async def query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await _execute_query(request, db, user["user_id"])


@router.post("/query/stream")
async def stream_query(
    request: QueryRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Stream query stages and answer tokens without cancelling durable work."""
    await _authorize_query(request, db, user["user_id"])
    operation_id = str(uuid.uuid4())
    queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue()
    sequence = 0
    terminal_emitted = False

    async def emit(event_type: str, data: dict[str, Any]) -> None:
        nonlocal sequence, terminal_emitted
        sequence += 1
        terminal_emitted = terminal_emitted or event_type in {"query.completed", "query.failed"}
        await queue.put(
            StreamEvent(
                id=f"{operation_id}:{sequence}",
                event=event_type,
                sequence=sequence,
                timestamp=utc_timestamp(),
                data={"operation_id": operation_id, **data},
            )
        )

    async def run_query() -> None:
        try:
            async with AsyncSessionLocal() as worker_db:
                await _execute_query(
                    request,
                    worker_db,
                    user["user_id"],
                    emit=emit,
                    stream_tokens=True,
                    route="rag-stream",
                )
        except Exception as exc:
            # _execute_query emits the terminal failure and finalizes durable
            # logging before the worker exits.
            if not terminal_emitted:
                detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
                await emit("query.failed", {"error": str(detail) or "Query failed"})
        finally:
            await queue.put(None)

    task = asyncio.create_task(run_query(), name=f"rag-query-{operation_id}")
    _query_stream_tasks.add(task)

    def release(completed: asyncio.Task) -> None:
        _query_stream_tasks.discard(completed)
        if not completed.cancelled():
            completed.exception()

    task.add_done_callback(release)

    async def events():
        while True:
            if await http_request.is_disconnected():
                return
            try:
                event = await asyncio.wait_for(
                    queue.get(),
                    timeout=settings.SSE_HEARTBEAT_SECONDS,
                )
            except TimeoutError:
                yield heartbeat_sse()
                continue
            if event is None:
                return
            yield format_sse(event)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/multimodal-query")
async def multimodal_query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Project).where(
            Project.id == request.project_id,
            Project.created_by == user["user_id"],
            Project.deleted_at.is_(None),
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(403, "Project not found or access denied")

    from app.services.chunkers.multimodal import embed_query_tokens

    query_vectors = await asyncio.to_thread(embed_query_tokens, request.question)
    collection = f"{project.collection}_multimodal"

    results = await asyncio.to_thread(
        qdrant.query_points,
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
    response = await asyncio.to_thread(
        client.chat.completions.create,
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
