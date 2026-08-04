import argparse
import json

from app.services.pipeline_artifacts import silver_to_gold
from jobs.control_plane import RAGForgeControlPlane


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ingestion-run-id", required=True)
    args = parser.parse_args()
    client = RAGForgeControlPlane()
    run = client.get_run(args.ingestion_run_id)
    latest_progress = {
        "stage": "queued",
        "embedding_model": run.get("embedding_model") or "BAAI/bge-small-en-v1.5",
        "total_chunks": 0,
        "embedded_chunks": 0,
    }

    def report_progress(progress: dict) -> None:
        latest_progress.update(progress)
        client.update_embedding_progress(args.ingestion_run_id, latest_progress)

    try:
        result = silver_to_gold(run, progress_callback=report_progress)
    except Exception as exc:
        client.update_embedding_progress(
            args.ingestion_run_id,
            {**latest_progress, "stage": "failed", "error_message": str(exc)},
        )
        raise
    print(
        json.dumps(
            result,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
