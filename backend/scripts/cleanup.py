try:
    from scripts._bootstrap import ensure_backend_path
except ModuleNotFoundError:
    try:
        from backend.scripts._bootstrap import ensure_backend_path
    except ModuleNotFoundError:
        from _bootstrap import ensure_backend_path

ensure_backend_path()

from app.services.indexer import delete_document_chunks

# Replace with your actual project's collection name
COLLECTION = "your_collection_name_here"
DOCUMENT_ID = "4028c7ef-17df-40ad-86bd-393dddb6974a"


def main() -> None:
    delete_document_chunks(document_id=DOCUMENT_ID, collection=COLLECTION)
    print("Deleted.")


if __name__ == "__main__":
    main()
