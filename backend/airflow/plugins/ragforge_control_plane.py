"""Airflow callbacks for RAGForge ingestion metadata."""

from jobs.control_plane import RAGForgeControlPlane


def ingestion_run_id_from_context(context: dict) -> str:
    ingestion_run_id = (context["dag_run"].conf or {}).get("ingestion_run_id")
    if not ingestion_run_id:
        raise ValueError("DAG run conf must contain ingestion_run_id")
    return ingestion_run_id


def record_task_status(
    context: dict,
    status: str,
    *,
    silver_path: str | None = None,
    gold_path: str | None = None,
) -> dict:
    run_id = ingestion_run_id_from_context(context)
    return RAGForgeControlPlane().update_status(
        run_id,
        status,
        airflow_dag_run_id=context["dag_run"].run_id,
        silver_path=silver_path,
        gold_path=gold_path,
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
