import logging

import httpx

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.repositories.ingestion_runs import update_ingestion_status


logger = logging.getLogger(__name__)


async def enqueue_ingestion(ingestion_run_id: str) -> str | None:
    """Trigger Airflow after the upload response and persist its DAG run ID."""
    if not settings.AIRFLOW_API_URL:
        return None

    dag_run_id = f"ragforge__{ingestion_run_id}"
    url = (
        f"{settings.AIRFLOW_API_URL.rstrip('/')}/api/v1/dags/"
        f"{settings.AIRFLOW_INGESTION_DAG_ID}/dagRuns"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                auth=(settings.AIRFLOW_USERNAME, settings.AIRFLOW_PASSWORD),
                json={
                    "dag_run_id": dag_run_id,
                    "conf": {"ingestion_run_id": ingestion_run_id},
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
        return dag_run_id
    except Exception:
        logger.exception("Could not enqueue ingestion run %s in Airflow", ingestion_run_id)
        return None
