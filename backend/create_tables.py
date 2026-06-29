# create a quick script to init the DB
import asyncio
from app.core.db import engine, Base
from app.models.tables import User, Project, Document  # import so Base knows about them

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created")

asyncio.run(main())