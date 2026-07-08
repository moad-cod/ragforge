import asyncio
from app.core.db import engine, Base
from app.models.tables import User, Project, Document
from app.core.config import settings
from qdrant_client import QdrantClient


def reset_qdrant():
    client = QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
    )
    collections = client.get_collections().collections
    for collection in collections:
        client.delete_collection(collection_name=collection.name)
    print(f"Deleted {len(collections)} Qdrant collection(s)")


async def main():
    reset_qdrant()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("Dropped and recreated all database tables")
    print("Development database and Qdrant reset complete")


if __name__ == "__main__":
    asyncio.run(main())
