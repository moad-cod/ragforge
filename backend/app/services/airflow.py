import logging
from datetime import UTC, datetime

import httpx

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.repositories.ingestion_runs import update_ingestion_status
from app.services.event_stream import publish_ingestion_event


logger = logging.getLogger(__name__)


async def enqueue_ingestion(ingestion_run_id: str) -> str | None:
    """Trigger Airflow after the upload response and persist its DAG run ID."""
    if not settings.AIRFLOW_API_URL:
        return None

    attempt_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    dag_run_id = f"ragforge__{ingestion_run_id}__{attempt_id}"
    base_url = settings.AIRFLOW_API_URL.rstrip("/")
    token_url = f"{base_url}/auth/token"
    dag_run_url = (
        f"{base_url}/api/v2/dags/"
        f"{settings.AIRFLOW_INGESTION_DAG_ID}/dagRuns"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_response = await client.post(
                token_url,
                json={
                    "username": settings.AIRFLOW_USERNAME,
                    "password": settings.AIRFLOW_PASSWORD,
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json()["access_token"]

            response = await client.post(
                dag_run_url,
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "dag_run_id": dag_run_id,
                    "conf": {"ingestion_run_id": ingestion_run_id},
                    # Required by Airflow 3.3's TriggerDAGRunPostBody. Null asks
                    # Airflow to assign the logical date at trigger time.
                    "logical_date": None,
                },
            )
            response.raise_for_status()

        async with AsyncSessionLocal() as db:
            await update_ingestion_status(
                db,
                ingestion_run_id,
                "queued",
                airflow_dag_run_id=dag_run_id,
            )
            await db.commit()
        await publish_ingestion_event(
            ingestion_run_id,
            "queued",
            data={"airflow_dag_run_id": dag_run_id},
        )
        return dag_run_id
    except Exception:
        logger.exception("Could not enqueue ingestion run %s in Airflow", ingestion_run_id)
        return None
