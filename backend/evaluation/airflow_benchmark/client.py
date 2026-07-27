"""Async FastAPI client used by the Airflow benchmark runner."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import time
import uuid
from typing import Any

import httpx

from evaluation.airflow_benchmark.models import utc_now
from evaluation.airflow_benchmark.validator import TERMINAL_STATUSES


@dataclass(frozen=True)
class BenchmarkIdentity:
    email: str
    password: str
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


class AirflowBenchmarkClient:
    def __init__(self, api_url: str, *, timeout_seconds: float = 240.0) -> None:
        self.api_url = api_url.rstrip("/")
        timeout = httpx.Timeout(timeout_seconds, connect=20.0, read=timeout_seconds)
        self.client = httpx.AsyncClient(base_url=self.api_url, timeout=timeout)

    async def close(self) -> None:
        await self.client.aclose()

    async def create_or_login_identity(
        self,
        *,
        email: str | None,
        password: str | None,
    ) -> BenchmarkIdentity:
        effective_password = password or "ragforge-airflow-benchmark"
        if email:
            token = await self.login(email=email, password=effective_password)
            return BenchmarkIdentity(email=email, password=effective_password, token=token)

        generated_email = f"airflow-benchmark-{uuid.uuid4().hex[:12]}@example.com"
        await self.register(
            email=generated_email,
            password=effective_password,
            full_name="Airflow Benchmark",
        )
        token = await self.login(email=generated_email, password=effective_password)
        return BenchmarkIdentity(email=generated_email, password=effective_password, token=token)

    async def register(self, *, email: str, password: str, full_name: str) -> dict[str, Any]:
        response = await self.client.post(
            "/auth/register",
            json={"email": email, "password": password, "full_name": full_name},
        )
        response.raise_for_status()
        return response.json()

    async def login(self, *, email: str, password: str) -> str:
        response = await self.client.post(
            "/auth/login",
            data={"username": email, "password": password},
        )
        response.raise_for_status()
        return str(response.json()["access_token"])

    async def create_project(self, identity: BenchmarkIdentity, *, name: str) -> dict[str, Any]:
        response = await self.client.post(
            "/projects/",
            headers=identity.headers,
            json={"name": name},
        )
        response.raise_for_status()
        return response.json()

    async def upload_file(
        self,
        identity: BenchmarkIdentity,
        *,
        project_id: str,
        filename: str,
        content: bytes,
        mime_type: str,
        chunker: str,
    ) -> dict[str, Any]:
        response = await self.client.post(
            "/ingest/file",
            headers=identity.headers,
            data={"project_id": project_id, "chunker": chunker},
            files={"file": (filename, content, mime_type)},
        )
        response.raise_for_status()
        return response.json()

    async def get_run(self, identity: BenchmarkIdentity, ingestion_run_id: str) -> dict[str, Any]:
        response = await self.client.get(
            f"/ingest/runs/{ingestion_run_id}",
            headers=identity.headers,
        )
        response.raise_for_status()
        return response.json()

    async def list_document_versions(
        self,
        identity: BenchmarkIdentity,
        document_id: str,
    ) -> list[dict[str, Any]]:
        response = await self.client.get(
            f"/documents/{document_id}/versions",
            headers=identity.headers,
        )
        response.raise_for_status()
        return list(response.json())

    async def wait_for_terminal_run(
        self,
        identity: BenchmarkIdentity,
        ingestion_run_id: str,
        *,
        poll_interval_seconds: float,
        timeout_seconds: float,
    ) -> tuple[dict[str, Any] | None, datetime]:
        deadline = time.monotonic() + timeout_seconds
        first_seen_at: datetime | None = None
        latest: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            latest = await self.get_run(identity, ingestion_run_id)
            first_seen_at = first_seen_at if first_seen_at is not None else utc_now()
            if latest.get("status") in TERMINAL_STATUSES:
                return latest, first_seen_at
            await asyncio.sleep(poll_interval_seconds)
        return latest, first_seen_at or utc_now()
