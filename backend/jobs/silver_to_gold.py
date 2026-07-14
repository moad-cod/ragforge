import argparse
import json

from app.services.pipeline_artifacts import silver_to_gold
from jobs.control_plane import RAGForgeControlPlane


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ingestion-run-id", required=True)
    args = parser.parse_args()
    run = RAGForgeControlPlane().get_run(args.ingestion_run_id)
    print(json.dumps(silver_to_gold(run), sort_keys=True))


if __name__ == "__main__":
    main()
