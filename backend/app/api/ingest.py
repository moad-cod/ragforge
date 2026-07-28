import time
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, UploadFile, File, Form, Header, HTTPException, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse
from app.core.auth import get_current_user
from app.core.db import AsyncSessionLocal, get_db
from app.models.tables import Project, Document, DocumentVersion
from app.repositories import document_versions as version_repository
from app.repositories import documents as document_repository
from app.repositories import ingestion_runs as ingestion_repository
from app.repositories import projects as project_repository
from app.services.parser import parse_document, parse_url, parse_gdrive
from app.services.embedder import embed_texts
from app.services.indexer import index_chunks, index_hierarchical_chunks, index_multimodal_pages
from app.services.chunkers.registry import (
    get_chunker,
    get_chunker_definition,
    get_default_chunker,
    validate_chunker,
)
from app.services.chunkers import late_chunking as late_chunking_module
from app.services.chunkers import hierarchical as hierarchical_module
from app.core.config import settings
from app.services.storage import delete_document_images
from app.services.bronze_storage import delete_raw_file, upload_raw_file
from app.services.event_stream import (
    INGESTION_SEQUENCE,
    StreamEvent,
    TERMINAL_INGESTION_STATUSES,
    durable_ingestion_event,
    format_sse,
    heartbeat_sse,
    publish_ingestion_event,
    replay_ingestion_events,
)
from app.services.ingestion_orchestrator import (
    enqueue_ingestion,
    ingestion_orchestration_enabled,
)
import asyncio
import hashlib
import uuid

router = APIRouter()

SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/csv",
    "text/html",
    "text/plain",
    "text/markdown",
}

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx", ".csv", ".html", ".htm", ".md", ".txt"}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_project(project_id: str, user_id: str, db: AsyncSession) -> Project:
    project = await project_repository.get_owned_project(db, project_id, user_id)
    if not project:
        raise HTTPException(403, "Project not found or access denied")
    return project

def _build_chunks(raw_text: list[str], chunker_id: str) -> list[str]:
    chunker = get_chunker(chunker_id)
    return chunker("\n\n".join(raw_text))

def _index(chunks: list[str], project_id: str, document_id: str, collection: str):
    if not chunks:
        raise HTTPException(400, "No indexable text was extracted from the document")
    embeddings = embed_texts(chunks)
    index_chunks(
        chunks=chunks,
        embeddings=embeddings,
        project_id=project_id,
        document_id=document_id,
        collection=collection,
    )

def _index_late_chunking(text: str, project_id: str, document_id: str, collection: str) -> list[str]:
    chunks, embeddings = late_chunking_module.chunk_with_embeddings(text)
    index_chunks(
        chunks=chunks,
        embeddings=embeddings,
        project_id=project_id,
        document_id=document_id,
        collection=collection,
    )
    return chunks

def _index_hierarchical(text: str, project_id: str, document_id: str, collection: str) -> list[str]:
    chunks = hierarchical_module.chunk_hierarchical(text, namespace=document_id)
    index_hierarchical_chunks(chunks, project_id, document_id, collection)
    return [c.text for c in chunks if c.chunk_type == "child"]

def _process_and_index(
    raw_text: list[str],
    chunker: str,
    project_id: str,
    document_id: str,
    collection: str,
) -> list[str]:
    """Single entry point for all chunking strategies."""
    full_text = "\n\n".join(raw_text)
    if chunker == "late_chunking":
        return _index_late_chunking(full_text, project_id, document_id, collection)
    elif chunker == "hierarchical":
        return _index_hierarchical(full_text, project_id, document_id, collection)
    else:
        chunks = _build_chunks(raw_text, chunker)
        _index(chunks, project_id, document_id, collection)
        return chunks

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


def _content_hash(data: bytes | str | list[str]) -> str:
    if isinstance(data, bytes):
        payload = data
    elif isinstance(data, list):
        payload = "\n\n".join(data).encode("utf-8", errors="ignore")
    else:
        payload = data.encode("utf-8", errors="ignore")
    return hashlib.sha256(payload).hexdigest()


def _object_prefix(project: Project, document_id: str, version_number: int) -> str:
    org_id = project.organization_id or "none"
    return f"org_id={org_id}/project_id={project.id}/document_id={document_id}/version={version_number}"


def _version_paths(
    project: Project,
    document_id: str,
    version_number: int,
    filename: str | None,
    source_type: str,
) -> tuple[str | None, str | None, str | None]:
    safe_name = (filename or source_type or "source").rsplit("/", 1)[-1] or "source"
    prefix = _object_prefix(project, document_id, version_number)
    bronze_path = f"bronze/{prefix}/raw/{safe_name}"
    silver_path = f"silver/{prefix}/chunks.parquet"
    gold_path = f"gold/{prefix}/embedded_chunks.parquet"
    return bronze_path, silver_path, gold_path


async def _next_version_number(db: AsyncSession, document_id: str) -> int:
    return await version_repository.get_latest_version_number(db, document_id) + 1


async def _get_or_create_document(
    db: AsyncSession,
    project: Project,
    filename: str,
    source_type: str,
    created_by: str,
    mime_type: str | None = None,
    extension: str | None = None,
    status: str = "processing",
) -> Document:
    doc = await document_repository.find_logical_document(db, project.id, filename, source_type)
    if doc:
        doc.status = status
        doc.mime_type = mime_type or doc.mime_type
        doc.extension = extension or doc.extension
        return doc

    return await document_repository.create_document(
        db,
        id=str(uuid.uuid4()),
        project_id=project.id,
        filename=filename,
        source_type=source_type,
        mime_type=mime_type,
        extension=extension,
        status=status,
        created_by=created_by,
    )


async def _add_document_version(
    db: AsyncSession,
    project: Project,
    document: Document,
    content_hash: str,
    source_type: str,
    filename: str | None,
    parser_name: str | None,
    chunker_id: str | None,
    status: str = "indexed",
    error_message: str | None = None,
) -> DocumentVersion:
    existing = await version_repository.get_version_by_content_hash(
        db,
        document.id,
        content_hash,
    )
    if existing:
        raise HTTPException(409, "This document content was already uploaded")

    version_number = await _next_version_number(db, document.id)
    bronze_path, silver_path, gold_path = _version_paths(
        project=project,
        document_id=document.id,
        version_number=version_number,
        filename=filename,
        source_type=source_type,
    )
    version = await version_repository.create_document_version(
        db,
        id=str(uuid.uuid4()),
        document_id=document.id,
        version_number=version_number,
        content_hash=content_hash,
        bronze_path=bronze_path,
        silver_path=silver_path,
        gold_path=gold_path,
        parser_name=parser_name,
        chunker_id=chunker_id,
        embedding_model=EMBEDDING_MODEL,
        status=status,
        error_message=error_message,
    )
    await document_repository.set_current_version(db, document.id, version.id)
    await document_repository.update_document_status(db, document.id, status)
    return version


async def _ensure_new_content(db: AsyncSession, document_id: str, content_hash: str) -> None:
    existing = await version_repository.get_version_by_content_hash(
        db,
        document_id,
        content_hash,
    )
    if existing:
        raise HTTPException(409, "This document content was already uploaded")


async def _save_document_version(
    db: AsyncSession,
    project: Project,
    document: Document,
    filename: str,
    source_type: str,
    content_hash: str,
    parser_name: str | None,
    chunker_id: str | None,
) -> tuple[Document, DocumentVersion]:
    version = await _add_document_version(
        db=db,
        project=project,
        document=document,
        content_hash=content_hash,
        source_type=source_type,
        filename=filename,
        parser_name=parser_name,
        chunker_id=chunker_id,
    )
    await db.commit()
    await db.refresh(document)
    await db.refresh(version)
    return document, version

def _extension(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()

async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File is too large. Max size is {settings.MAX_UPLOAD_BYTES} bytes")
    return data

def _validate_file(file: UploadFile):
    ext = _extension(file.filename)
    if ext not in SUPPORTED_EXTENSIONS and file.content_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(400, f"Unsupported file type: {file.content_type or ext or 'unknown'}")

def _ingest_text_document(
    file_bytes: bytes,
    filename: str,
    chunker: str,
    project_id: str,
    document_id: str,
    collection: str,
) -> list[str]:
    raw_text = parse_document(file_bytes, filename)
    return _process_and_index(raw_text, chunker, project_id, document_id, collection)

def _validate_text_chunker(chunker_id: str) -> str:
    try:
        chunker_id = validate_chunker(chunker_id)
        definition = get_chunker_definition(chunker_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if definition.requires_multimodal:
        raise HTTPException(400, "Chunker 'multimodal' is available through /ingest/multimodal, not text ingestion.")
    return chunker_id

async def _cleanup_document_artifacts(document_id: str, collection: str, source: str):
    from app.services.indexer import delete_document_chunks
    try:
        await asyncio.to_thread(delete_document_chunks, document_id=document_id, collection=collection)
    except Exception:
        pass
    if source == "multimodal":
        try:
            await asyncio.to_thread(delete_document_images, document_id)
        except Exception:
            pass

def _debug_payload(chunks: list[str]) -> dict:
    if not settings.DEBUG_RETURN_CONTEXT:
        return {}
    return {"sample_chunks": chunks[:3]}


# ── 1. File upload ────────────────────────────────────────────────────────────
@router.post("/multimodal")
async def upload_multimodal(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if file.content_type != "application/pdf":
        raise HTTPException(400, "Multimodal ingestion only supports PDF files")
    try:
        settings.require_r2()
    except ValueError as exc:
        raise HTTPException(503, str(exc))

    project = await _get_project(project_id, user["user_id"], db)
    file_bytes = await _read_upload(file)
    file_hash = _content_hash(file_bytes)
    doc = await _get_or_create_document(
        db=db,
        project=project,
        filename=file.filename,
        source_type="multimodal",
        created_by=user["user_id"],
        mime_type=file.content_type,
        extension=_extension(file.filename),
    )
    await _ensure_new_content(db, doc.id, file_hash)

    try:
        from app.services.chunkers.multimodal import ingest_pdf_multimodal

        page_embeddings, page_image_urls, num_pages = await asyncio.to_thread(
            ingest_pdf_multimodal, file_bytes, doc.id, settings.MAX_MULTIMODAL_PAGES
        )

        collection = f"{project.collection}_multimodal"
        await asyncio.to_thread(
            index_multimodal_pages,
            page_embeddings=page_embeddings,
            page_image_urls=page_image_urls,
            project_id=project_id,
            document_id=doc.id,
            collection=collection,
        )

        doc, version = await _save_document_version(
            db=db,
            project=project,
            document=doc,
            filename=file.filename,
            source_type="multimodal",
            content_hash=file_hash,
            parser_name="pymupdf",
            chunker_id="multimodal",
        )
    except ValueError as exc:
        await _cleanup_document_artifacts(doc.id, f"{project.collection}_multimodal", "multimodal")
        raise HTTPException(413, str(exc))
    except Exception:
        await _cleanup_document_artifacts(doc.id, f"{project.collection}_multimodal", "multimodal")
        raise

    return {
        "document_id": doc.id,
        "document_version_id": version.id,
        "version_number": version.version_number,
        "project_id": project_id,
        "collection": collection,
        "filename": file.filename,
        "source_type": "multimodal",
        "mime_type": file.content_type,
        "extension": _extension(file.filename),
        "status": "indexed",
        "pages_indexed": num_pages,
        "page_image_urls": page_image_urls,
    }
class FileLandingResponse(BaseModel):
    document_id: str
    document_version_id: str
    ingestion_run_id: str
    status: str


class IngestionProgress(BaseModel):
    bronze: bool
    silver: bool
    gold: bool
    qdrant: bool


class IngestionRunResponse(BaseModel):
    ingestion_run_id: str
    document_id: str
    document_version_id: str
    status: str
    airflow_dag_run_id: str | None
    error_message: str | None
    progress: IngestionProgress
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


def _ingestion_run_payload(run, version) -> dict:
    silver_complete = run.status in {"silver_completed", "gold_completed", "indexed"}
    gold_complete = run.status in {"gold_completed", "indexed"}
    return {
        "ingestion_run_id": run.id,
        "document_id": run.document_id,
        "document_version_id": run.document_version_id,
        "status": run.status,
        "airflow_dag_run_id": run.airflow_dag_run_id,
        "error_message": run.error_message,
        "created_at": getattr(run, "created_at", datetime.now(timezone.utc)),
        "started_at": getattr(run, "started_at", None),
        "finished_at": getattr(run, "finished_at", None),
        "progress": {
            "bronze": bool(version.bronze_path),
            "silver": bool(version.silver_path) or silver_complete,
            "gold": bool(version.gold_path) or gold_complete,
            "qdrant": run.status == "indexed",
        },
    }


@router.post("/file", response_model=FileLandingResponse, status_code=202)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: str = Form(...),
    chunker: str = Form(default=get_default_chunker().id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    project = await _get_project(project_id, user["user_id"], db)
    _validate_file(file)
    chunker = _validate_text_chunker(chunker)

    filename = file.filename or "upload"
    file_bytes = await _read_upload(file)
    file_hash = _content_hash(file_bytes)
    doc = await _get_or_create_document(
        db=db,
        project=project,
        filename=filename,
        source_type="file",
        created_by=user["user_id"],
        mime_type=file.content_type,
        extension=_extension(file.filename),
        status="landed",
    )
    await _ensure_new_content(db, doc.id, file_hash)

    version_number = await _next_version_number(db, doc.id)
    bronze_path, _, _ = _version_paths(
        project=project,
        document_id=doc.id,
        version_number=version_number,
        filename=filename,
        source_type="file",
    )
    uploaded = False
    try:
        await asyncio.to_thread(
            upload_raw_file,
            file_bytes,
            bronze_path,
            file.content_type,
        )
        uploaded = True
        version = await version_repository.create_document_version(
            db,
            id=str(uuid.uuid4()),
            document_id=doc.id,
            version_number=version_number,
            content_hash=file_hash,
            bronze_path=bronze_path,
            silver_path=None,
            gold_path=None,
            parser_name=_extension(file.filename).lstrip(".") or "auto",
            chunker_id=chunker,
            embedding_model=EMBEDDING_MODEL,
            status="landed",
            error_message=None,
        )
        run = await ingestion_repository.create_ingestion_run(
            db,
            id=str(uuid.uuid4()),
            project_id=project.id,
            document_id=doc.id,
            document_version_id=version.id,
            status="landed",
            created_by=user["user_id"],
        )
        await db.commit()
    except Exception:
        await db.rollback()
        if uploaded:
            try:
                await asyncio.to_thread(delete_raw_file, bronze_path)
            except Exception:
                pass
        raise

    await publish_ingestion_event(
        run.id,
        "landed",
        data={"document_id": doc.id, "document_version_id": version.id},
    )

    if ingestion_orchestration_enabled():
        background_tasks.add_task(enqueue_ingestion, run.id)

    return {
        "document_id": doc.id,
        "document_version_id": version.id,
        "ingestion_run_id": run.id,
        "status": "landed",
    }


@router.get("/runs/{ingestion_run_id}", response_model=IngestionRunResponse)
async def get_ingestion_run_status(
    ingestion_run_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    run = await ingestion_repository.get_owned_ingestion_run(
        db,
        ingestion_run_id,
        user["user_id"],
    )
    if run is None:
        raise HTTPException(404, "Ingestion run not found")

    version = await version_repository.get_document_version(db, run.document_version_id)
    if version is None:
        raise HTTPException(500, "Ingestion run has no document version")

    return _ingestion_run_payload(run, version)


@router.get("/runs", response_model=list[IngestionRunResponse])
async def list_ingestion_runs(
    project_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    await _get_project(project_id, user["user_id"], db)
    runs = await ingestion_repository.list_owned_project_runs(
        db,
        project_id,
        user["user_id"],
        limit=limit,
    )
    payloads: list[dict] = []
    for run in runs:
        version = await version_repository.get_document_version(db, run.document_version_id)
        if version is not None:
            payloads.append(_ingestion_run_payload(run, version))
    return payloads


@router.post("/runs/{ingestion_run_id}/retry", response_model=IngestionRunResponse)
async def retry_ingestion_run(
    ingestion_run_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    run = await ingestion_repository.get_owned_ingestion_run(
        db,
        ingestion_run_id,
        user["user_id"],
    )
    if run is None:
        raise HTTPException(404, "Ingestion run not found")
    try:
        run = await ingestion_repository.retry_failed_ingestion_run(db, run.id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

    await db.commit()
    version = await version_repository.get_document_version(db, run.document_version_id)
    if version is None:
        raise HTTPException(500, "Ingestion run has no document version")

    await publish_ingestion_event(
        run.id,
        "queued",
        data={"document_id": run.document_id, "document_version_id": run.document_version_id},
    )
    if ingestion_orchestration_enabled():
        background_tasks.add_task(enqueue_ingestion, run.id)
    return _ingestion_run_payload(run, version)


@router.get("/runs/{ingestion_run_id}/events")
async def stream_ingestion_run_events(
    request: Request,
    ingestion_run_id: str,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Stream tenant-owned ingestion progress with Redis replay and DB recovery."""
    run = await ingestion_repository.get_owned_ingestion_run(
        db,
        ingestion_run_id,
        user["user_id"],
    )
    if run is None:
        raise HTTPException(404, "Ingestion run not found")
    version = await version_repository.get_document_version(db, run.document_version_id)
    if version is None:
        raise HTTPException(500, "Ingestion run has no document version")

    initial_payload = _ingestion_run_payload(run, version)
    initial = durable_ingestion_event(
        ingestion_run_id,
        run.status,
        data=initial_payload,
        snapshot=True,
    )

    async def events():
        yield format_sse(initial)
        if initial.data["status"] in TERMINAL_INGESTION_STATUSES:
            return

        last_status_rank = INGESTION_SEQUENCE.get(initial.data["status"], 0)
        last_event_sequence = initial.sequence
        seen_event_ids = {initial.id}
        cursor = last_event_id or "0-0"
        last_heartbeat = time.monotonic()

        while True:
            if await request.is_disconnected():
                return

            replay = await replay_ingestion_events(ingestion_run_id, cursor)
            for event in replay.events:
                cursor = event.id
                if event.id in seen_event_ids:
                    continue
                seen_event_ids.add(event.id)
                event_status = event.data.get("status")
                event_status_rank = INGESTION_SEQUENCE.get(event_status, 0)
                if event_status_rank <= last_status_rank or event.sequence <= last_event_sequence:
                    continue
                last_status_rank = event_status_rank
                last_event_sequence = event.sequence
                yield format_sse(event)
                if event_status in TERMINAL_INGESTION_STATUSES:
                    return

            async with AsyncSessionLocal() as stream_db:
                current = await ingestion_repository.get_ingestion_run(stream_db, ingestion_run_id)
                if current is None:
                    return
                current_version = await version_repository.get_document_version(
                    stream_db,
                    current.document_version_id,
                )
                if current_version is None:
                    return
                durable_rank = INGESTION_SEQUENCE.get(current.status, 0)
                if durable_rank > last_status_rank:
                    current_payload = _ingestion_run_payload(current, current_version)
                    durable_event = durable_ingestion_event(
                        ingestion_run_id,
                        current.status,
                        data=current_payload,
                    )
                    next_sequence = max(durable_event.sequence, last_event_sequence + 1)
                    event = StreamEvent(
                        id=f"durable-{next_sequence}-{current.status}",
                        event=durable_event.event,
                        sequence=next_sequence,
                        timestamp=durable_event.timestamp,
                        data=durable_event.data,
                    )
                    last_status_rank = durable_rank
                    last_event_sequence = event.sequence
                    yield format_sse(event)
                    if current.status in TERMINAL_INGESTION_STATUSES:
                        return

            now = time.monotonic()
            if now - last_heartbeat >= settings.SSE_HEARTBEAT_SECONDS:
                yield heartbeat_sse()
                last_heartbeat = now
            await asyncio.sleep(settings.SSE_POLL_SECONDS)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


# ── 2. URL scrape ─────────────────────────────────────────────────────────────

class URLPayload(BaseModel):
    url: str
    project_id: str
    chunker: str = get_default_chunker().id

@router.post("/url")
async def upload_url(
    payload: URLPayload,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    project = await _get_project(payload.project_id, user["user_id"], db)
    chunker = _validate_text_chunker(payload.chunker)
    raw_text = await parse_url(payload.url)
    source_hash = _content_hash(raw_text)
    doc = await _get_or_create_document(
        db=db,
        project=project,
        filename=payload.url,
        source_type="url",
        created_by=user["user_id"],
    )
    await _ensure_new_content(db, doc.id, source_hash)

    try:
        chunks = await asyncio.to_thread(
            _process_and_index,
            raw_text,
            chunker,
            payload.project_id,
            doc.id,
            project.collection,
        )
        doc, version = await _save_document_version(
            db=db,
            project=project,
            document=doc,
            filename=payload.url,
            source_type="url",
            content_hash=source_hash,
            parser_name="url",
            chunker_id=chunker,
        )
    except Exception:
        await _cleanup_document_artifacts(doc.id, project.collection, "url")
        raise

    return {
        "document_id": doc.id,
        "document_version_id": version.id,
        "version_number": version.version_number,
        "project_id": payload.project_id,
        "collection": project.collection,
        "url": payload.url,
        "source_type": "url",
        "status": "indexed",
        "chunker": chunker,
        "chunks_indexed": len(chunks),
        **_debug_payload(chunks),
    }


# ── 3. Google Drive ───────────────────────────────────────────────────────────

class GDrivePayload(BaseModel):
    file_id: str
    access_token: str
    project_id: str
    chunker: str = get_default_chunker().id

@router.post("/gdrive")
async def upload_gdrive(
    payload: GDrivePayload,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    project = await _get_project(payload.project_id, user["user_id"], db)
    chunker = _validate_text_chunker(payload.chunker)
    raw_text = await parse_gdrive(payload.file_id, payload.access_token)
    source_hash = _content_hash(raw_text)
    doc = await _get_or_create_document(
        db=db,
        project=project,
        filename=payload.file_id,
        source_type="gdrive",
        created_by=user["user_id"],
    )
    await _ensure_new_content(db, doc.id, source_hash)

    try:
        chunks = await asyncio.to_thread(
            _process_and_index,
            raw_text,
            chunker,
            payload.project_id,
            doc.id,
            project.collection,
        )
        doc, version = await _save_document_version(
            db=db,
            project=project,
            document=doc,
            filename=payload.file_id,
            source_type="gdrive",
            content_hash=source_hash,
            parser_name="gdrive",
            chunker_id=chunker,
        )
    except Exception:
        await _cleanup_document_artifacts(doc.id, project.collection, "gdrive")
        raise

    return {
        "document_id": doc.id,
        "document_version_id": version.id,
        "version_number": version.version_number,
        "project_id": payload.project_id,
        "collection": project.collection,
        "file_id": payload.file_id,
        "source_type": "gdrive",
        "status": "indexed",
        "chunker": chunker,
        "chunks_indexed": len(chunks),
        **_debug_payload(chunks),
    }
