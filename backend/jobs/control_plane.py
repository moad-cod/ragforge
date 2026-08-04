"""Dependency-free HTTP client shared by Airflow and pipeline commands."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class RAGForgeControlPlane:
    def __init__(self) -> None:
        self.base_url = os.environ.get("RAGFORGE_API_URL", "http://fastapi:8000").rstrip("/")
        self.token = os.environ.get("PIPELINE_SERVICE_TOKEN", "")
        if not self.token:
            raise RuntimeError("PIPELINE_SERVICE_TOKEN is required by pipeline jobs")

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        body = json.dumps(payload).encode() if payload is not None else None
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode())
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(
                f"RAGForge control-plane request failed: {exc.code} {detail}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(f"RAGForge control-plane is unavailable: {exc.reason}") from exc

    def get_run(self, ingestion_run_id: str) -> dict:
        return self._request("GET", f"/internal/pipeline/ingestion-runs/{ingestion_run_id}")

    def update_status(
        self,
        ingestion_run_id: str,
        status: str,
        *,
        airflow_dag_run_id: str | None = None,
        error_message: str | None = None,
        silver_path: str | None = None,
        gold_path: str | None = None,
    ) -> dict:
        return self._request(
            "PATCH",
            f"/internal/pipeline/ingestion-runs/{ingestion_run_id}",
            {
                "status": status,
                "airflow_dag_run_id": airflow_dag_run_id,
                "error_message": error_message,
                "silver_path": silver_path,
                "gold_path": gold_path,
            },
        )

    def update_embedding_progress(self, ingestion_run_id: str, progress: dict) -> dict:
        return self._request(
            "PATCH",
            f"/internal/pipeline/ingestion-runs/{ingestion_run_id}/embedding-progress",
            progress,
        )

    def index_chunks(self, ingestion_run_id: str, chunks: list[dict]) -> dict:
        return self._request(
            "POST",
            f"/internal/pipeline/ingestion-runs/{ingestion_run_id}/chunks/index",
            {"chunks": chunks},
        )
