import asyncio
from app.core.db import engine, Base
from app.models.tables import User, Project, Document
from app.core.config import settings
from qdrant_client import QdrantClient


def reset_qdrant() -> int:
    client = QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
    )
    collections = client.get_collections().collections
    for collection in collections:
        client.delete_collection(collection_name=collection.name)
    return len(collections)


async def rebuild_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def main():
    print("Resetting RAGForge development state...")
    deleted_collections = reset_qdrant()
    print(f"Deleted {deleted_collections} Qdrant collection(s)")

    await rebuild_tables()
    await engine.dispose()
    print("Dropped and recreated all database tables")
    print("Fresh development reset complete. You can run test_chunkers.sh again.")


if __name__ == "__main__":
    asyncio.run(main())
