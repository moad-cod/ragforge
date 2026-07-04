from app.services.indexer import delete_document_chunks

# Replace with your actual project's collection name
COLLECTION = "your_collection_name_here"
DOCUMENT_ID = "4028c7ef-17df-40ad-86bd-393dddb6974a"

delete_document_chunks(document_id=DOCUMENT_ID, collection=COLLECTION)
print("Deleted.")