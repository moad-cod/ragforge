"""Small dependency-free Airflow client for RAGForge ingestion metadata."""
import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class RAGForgeControlPlane:
    def __init__(self) -> None:
        self.base_url = os.environ.get("RAGFORGE_API_URL", "http://fastapi:8000").rstrip("/")
        self.token = os.environ.get("PIPELINE_SERVICE_TOKEN", "")
        if not self.token:
            raise RuntimeError("PIPELINE_SERVICE_TOKEN is required by Airflow jobs")

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
            with urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode())
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"RAGForge control-plane request failed: {exc.code} {detail}") from exc

    def get_run(self, ingestion_run_id: str) -> dict:
        return self._request("GET", f"/internal/pipeline/ingestion-runs/{ingestion_run_id}")

    def update_status(
        self,
        ingestion_run_id: str,
        status: str,
        *,
        airflow_dag_run_id: str | None = None,
        error_message: str | None = None,
    ) -> dict:
        return self._request(
            "PATCH",
            f"/internal/pipeline/ingestion-runs/{ingestion_run_id}",
            {
                "status": status,
                "airflow_dag_run_id": airflow_dag_run_id,
                "error_message": error_message,
            },
        )

    def index_chunks(self, ingestion_run_id: str, chunks: list[dict]) -> dict:
        """Send embedded Gold chunks through the durable indexing boundary."""
        return self._request(
            "POST",
            f"/internal/pipeline/ingestion-runs/{ingestion_run_id}/chunks/index",
            {"chunks": chunks},
        )


def ingestion_run_id_from_context(context: dict) -> str:
    ingestion_run_id = (context["dag_run"].conf or {}).get("ingestion_run_id")
    if not ingestion_run_id:
        raise ValueError("DAG run conf must contain ingestion_run_id")
    return ingestion_run_id


def record_task_status(context: dict, status: str) -> dict:
    run_id = ingestion_run_id_from_context(context)
    return RAGForgeControlPlane().update_status(
        run_id,
        status,
        airflow_dag_run_id=context["dag_run"].run_id,
    )


def mark_task_failure(context: dict) -> None:
    run_id = ingestion_run_id_from_context(context)
    error = str(context.get("exception") or "Airflow task failed")
    RAGForgeControlPlane().update_status(
        run_id,
        "failed",
        airflow_dag_run_id=context["dag_run"].run_id,
        error_message=error,
    )
