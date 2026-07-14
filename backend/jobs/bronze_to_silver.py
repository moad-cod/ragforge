import argparse
import json

from app.services.pipeline_artifacts import bronze_to_silver
from jobs.control_plane import RAGForgeControlPlane


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ingestion-run-id", required=True)
    args = parser.parse_args()
    run = RAGForgeControlPlane().get_run(args.ingestion_run_id)
    print(json.dumps(bronze_to_silver(run), sort_keys=True))


if __name__ == "__main__":
    main()
