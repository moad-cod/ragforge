"""Shared clients and assertions for the Task 26 container test suite."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from io import BytesIO
import json
import os
import time
import uuid
from typing import Any

import boto3
import httpx
import pyarrow.parquet as pq
from botocore.config import Config
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models import (
    Chunk,
    Document,
    DocumentVersion,
    IngestionRun,
    QueryLog,
    RetrievalLog,
)


API_URL = os.getenv("E2E_API_URL", "http://localhost:8000").rstrip("/")
AIRFLOW_URL = os.getenv("E2E_AIRFLOW_URL", "http://airflow-apiserver:8080").rstrip("/")
PROVIDER_URL = os.getenv("E2E_PROVIDER_URL", "http://provider-stub:8090").rstrip("/")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
TERMINAL_INGESTION_STATUSES = {"indexed", "failed", "cancelled"}
INGESTION_RANK = {
    "landed": 1,
    "queued": 2,
    "running": 3,
    "silver_completed": 4,
    "gold_completed": 5,
    "indexed": 6,
    "failed": 7,
    "cancelled": 7,
}


def unique_name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def representative_document(marker: str) -> bytes:
    sentence = (
        f"{marker} confirms that RAGForge stores raw files in Bronze, cleaned chunks "
        "in Silver Parquet, embedded metadata in Gold Parquet, vectors in Qdrant, "
        "and durable lineage in PostgreSQL. "
    )
    return (sentence * 12).encode("utf-8")


@dataclass(frozen=True)
class Identity:
    email: str
    password: str
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


class E2EHarness:
    def __init__(self) -> None:
        timeout = httpx.Timeout(240.0, connect=20.0, read=240.0)
        self.api = httpx.AsyncClient(base_url=API_URL, timeout=timeout)
        self.provider = httpx.AsyncClient(base_url=PROVIDER_URL, timeout=20.0)
        self.minio = boto3.client(
            "s3",
            endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "ragforge"),
            aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "ragforge123"),
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self.qdrant = QdrantClient(url=QDRANT_URL, check_compatibility=False)
        self.engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def close(self) -> None:
        await self.api.aclose()
        await self.provider.aclose()
        await self.engine.dispose()
        self.qdrant.close()

    async def create_identity(self, prefix: str = "e2e") -> Identity:
        email = f"{unique_name(prefix)}@example.com"
        password = "ragforge-e2e-password"
        response = await self.api.post(
            "/auth/register",
            json={"email": email, "password": password, "full_name": "Task 26"},
        )
        response.raise_for_status()
        login = await self.api.post(
            "/auth/login",
            data={"username": email, "password": password},
        )
        login.raise_for_status()
        return Identity(email=email, password=password, token=login.json()["access_token"])

    async def create_project(self, identity: Identity, prefix: str = "task-26") -> dict:
        response = await self.api.post(
            "/projects/",
            headers=identity.headers,
            json={"name": unique_name(prefix)},
        )
        response.raise_for_status()
        return response.json()

    async def upload(
        self,
        identity: Identity,
        project_id: str,
        *,
        filename: str,
        content: bytes,
    ) -> dict:
        response = await self.api.post(
            "/ingest/file",
            headers=identity.headers,
            data={"project_id": project_id, "chunker": "paragraph"},
            files={"file": (filename, content, "text/plain")},
        )
        response.raise_for_status()
        payload = response.json()
        if response.status_code != 202 or payload["status"] != "landed":
            raise AssertionError(f"Unexpected upload response: {response.status_code} {payload}")
        return payload

    async def wait_for_ingestion(
        self,
        identity: Identity,
        run_id: str,
        *,
        expected: str,
        timeout: float = 240.0,
    ) -> dict:
        deadline = time.monotonic() + timeout
        latest: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            response = await self.api.get(
                f"/ingest/runs/{run_id}",
                headers=identity.headers,
            )
            response.raise_for_status()
            latest = response.json()
            if latest["status"] == expected:
                return latest
            if latest["status"] in TERMINAL_INGESTION_STATUSES:
                raise AssertionError(
                    f"Ingestion reached {latest['status']!r}, expected {expected!r}: "
                    f"{latest.get('error_message')}"
                )
            await asyncio.sleep(0.5)
        raise AssertionError(f"Ingestion did not reach {expected!r}; latest={latest}")

    async def collect_ingestion_events(
        self,
        identity: Identity,
        run_id: str,
    ) -> list[dict[str, Any]]:
        return await self._collect_sse(
            "GET",
            f"/ingest/runs/{run_id}/events",
            headers=identity.headers,
            terminal_events={
                "ingestion.completed",
                "ingestion.failed",
                "ingestion.cancelled",
            },
        )

    async def stream_query(
        self,
        identity: Identity,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return await self._collect_sse(
            "POST",
            "/rag/query/stream",
            headers=identity.headers,
            json_payload=payload,
            terminal_events={"query.completed", "query.failed"},
        )

    async def _collect_sse(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        terminal_events: set[str],
        json_payload: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        event_name: str | None = None
        data_lines: list[str] = []
        async with self.api.stream(
            method,
            path,
            headers=headers,
            json=json_payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith(":"):
                    continue
                if line.startswith("event:"):
                    event_name = line.partition(":")[2].strip()
                elif line.startswith("data:"):
                    data_lines.append(line.partition(":")[2].strip())
                elif not line and data_lines:
                    payload = json.loads("\n".join(data_lines))
                    payload.setdefault("event", event_name)
                    events.append(payload)
                    if payload.get("event") in terminal_events:
                        return events
                    event_name = None
                    data_lines = []
        return events

    async def set_provider_failure(self, enabled: bool) -> None:
        response = await self.provider.post(
            "/control/failure",
            json={"enabled": enabled},
        )
        response.raise_for_status()

    async def wait_for_airflow_success(self, dag_run_id: str, timeout: float = 120.0) -> dict:
        async with httpx.AsyncClient(timeout=20.0) as client:
            token_response = await client.post(
                f"{AIRFLOW_URL}/auth/token",
                json={"username": "admin", "password": "admin"},
            )
            token_response.raise_for_status()
            headers = {
                "Authorization": f"Bearer {token_response.json()['access_token']}"
            }
            deadline = time.monotonic() + timeout
            latest: dict[str, Any] | None = None
            while time.monotonic() < deadline:
                response = await client.get(
                    f"{AIRFLOW_URL}/api/v2/dags/ragforge_ingestion/dagRuns/{dag_run_id}",
                    headers=headers,
                )
                response.raise_for_status()
                latest = response.json()
                if latest.get("state") == "success":
                    return latest
                if latest.get("state") == "failed":
                    raise AssertionError(f"Airflow DAG failed: {latest}")
                await asyncio.sleep(0.5)
        raise AssertionError(f"Airflow DAG did not succeed; latest={latest}")

    def read_object(self, path: str) -> bytes:
        bucket, separator, key = path.partition("/")
        if not separator:
            raise AssertionError(f"Invalid object path {path!r}")
        return self.minio.get_object(Bucket=bucket, Key=key)["Body"].read()

    def parquet_rows(self, path: str) -> list[dict[str, Any]]:
        return pq.read_table(BytesIO(self.read_object(path))).to_pylist()

    def qdrant_points(self, collection: str, version_id: str):
        records, _ = self.qdrant.scroll(
            collection_name=collection,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="document_version_id",
                        match=MatchValue(value=version_id),
                    )
                ]
            ),
            limit=1000,
            with_payload=True,
            with_vectors=False,
        )
        return records

    async def ingestion_graph(self, run_id: str) -> dict[str, Any]:
        async with self.sessions() as db:
            run = await db.get(IngestionRun, run_id)
            if run is None:
                raise AssertionError(f"Missing ingestion run {run_id}")
            document = await db.get(Document, run.document_id)
            version = await db.get(DocumentVersion, run.document_version_id)
            chunks = list(
                (
                    await db.execute(
                        select(Chunk)
                        .where(Chunk.document_version_id == run.document_version_id)
                        .order_by(Chunk.chunk_index)
                    )
                )
                .scalars()
                .all()
            )
            return {
                "run": run,
                "document": document,
                "version": version,
                "chunks": chunks,
            }

    async def query_graph(self, query_log_id: str) -> dict[str, Any]:
        async with self.sessions() as db:
            query_log = await db.get(QueryLog, query_log_id)
            retrievals = list(
                (
                    await db.execute(
                        select(RetrievalLog)
                        .where(RetrievalLog.query_log_id == query_log_id)
                        .order_by(RetrievalLog.rank)
                    )
                )
                .scalars()
                .all()
            )
            chunks = {
                chunk.id: chunk
                for chunk in (
                    (
                        await db.execute(
                            select(Chunk).where(
                                Chunk.id.in_(
                                    [
                                        row.chunk_id
                                        for row in retrievals
                                        if row.chunk_id is not None
                                    ]
                                )
                            )
                        )
                    )
                    .scalars()
                    .all()
                    if retrievals
                    else []
                )
            }
            return {
                "query_log": query_log,
                "retrievals": retrievals,
                "chunks": chunks,
            }

    async def latest_query_for_question(
        self,
        project_id: str,
        question: str,
    ) -> QueryLog | None:
        async with self.sessions() as db:
            return (
                await db.execute(
                    select(QueryLog)
                    .where(
                        QueryLog.project_id == project_id,
                        QueryLog.question == question,
                    )
                    .order_by(QueryLog.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
