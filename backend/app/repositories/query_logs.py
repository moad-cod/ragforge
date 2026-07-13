from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import QueryLog


async def create_query_log(db: AsyncSession, **values) -> QueryLog:
    query_log = QueryLog(**values)
    db.add(query_log)
    await db.flush()
    return query_log


async def update_query_scores(
    db: AsyncSession,
    query_log_id: str,
    *,
    relevance_score: float | None = None,
    groundedness_score: float | None = None,
) -> QueryLog | None:
    query_log = await db.get(QueryLog, query_log_id)
    if query_log is not None:
        query_log.relevance_score = relevance_score
        query_log.groundedness_score = groundedness_score
        await db.flush()
    return query_log


async def finish_query_log(
    db: AsyncSession,
    query_log: QueryLog,
    *,
    latency_ms: int,
    cache_hit: bool,
    route: str,
) -> QueryLog:
    query_log.latency_ms = latency_ms
    query_log.cache_hit = cache_hit
    query_log.route = route
    await db.flush()
    return query_log


async def get_project_query_history(
    db: AsyncSession,
    project_id: str,
    *,
    limit: int = 100,
) -> list[QueryLog]:
    result = await db.execute(
        select(QueryLog)
        .where(QueryLog.project_id == project_id)
        .order_by(QueryLog.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
