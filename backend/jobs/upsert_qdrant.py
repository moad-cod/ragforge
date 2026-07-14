import argparse
import json

from app.services.pipeline_artifacts import gold_chunks
from jobs.control_plane import RAGForgeControlPlane


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ingestion-run-id", required=True)
    args = parser.parse_args()
    client = RAGForgeControlPlane()
    run = client.get_run(args.ingestion_run_id)
    result = client.index_chunks(args.ingestion_run_id, gold_chunks(run))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
