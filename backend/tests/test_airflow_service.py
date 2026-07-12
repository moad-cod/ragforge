import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.core.config import settings
from app.services.airflow import enqueue_ingestion


class _Response:
    def __init__(self, payload=None):
        self.payload = payload or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _HTTPClient:
    def __init__(self, calls, **_kwargs):
        self.calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url.endswith("/auth/token"):
            return _Response({"access_token": "airflow-jwt"})
        return _Response()


class _DatabaseContext:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *_args):
        return None


class AirflowServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_enqueue_uses_airflow_3_jwt_and_public_api_v2(self):
        calls = []
        db = SimpleNamespace(commit=AsyncMock())

        with (
            patch.object(settings, "AIRFLOW_API_URL", "http://airflow-apiserver:8080"),
            patch.object(settings, "AIRFLOW_USERNAME", "admin"),
            patch.object(settings, "AIRFLOW_PASSWORD", "secret"),
            patch.object(settings, "AIRFLOW_INGESTION_DAG_ID", "ragforge_ingestion"),
            patch(
                "app.services.airflow.httpx.AsyncClient",
                side_effect=lambda **kwargs: _HTTPClient(calls, **kwargs),
            ),
            patch(
                "app.services.airflow.AsyncSessionLocal",
                side_effect=lambda: _DatabaseContext(db),
            ),
            patch(
                "app.services.airflow.update_ingestion_status",
                AsyncMock(),
            ) as update_status,
        ):
            result = await enqueue_ingestion("run-id")

        self.assertEqual(result, "ragforge__run-id")
        self.assertEqual(calls[0][0], "http://airflow-apiserver:8080/auth/token")
        self.assertEqual(
            calls[0][1]["json"],
            {"username": "admin", "password": "secret"},
        )
        self.assertEqual(
            calls[1][0],
            "http://airflow-apiserver:8080/api/v2/dags/ragforge_ingestion/dagRuns",
        )
        self.assertEqual(calls[1][1]["headers"], {"Authorization": "Bearer airflow-jwt"})
        self.assertEqual(calls[1][1]["json"]["conf"], {"ingestion_run_id": "run-id"})
        self.assertEqual(update_status.await_args.args[1], "run-id")
        self.assertEqual(update_status.await_args.args[2], "queued")
        db.commit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
