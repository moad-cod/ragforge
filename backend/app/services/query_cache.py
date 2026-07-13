"""Best-effort Redis cache for RAG query results."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from app.core.config import settings


logger = logging.getLogger(__name__)
_redis = None


def _client():
    global _redis
    if not settings.REDIS_URL:
        return None
    if _redis is None:
        import redis.asyncio as redis

        _redis = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
    return _redis


def cache_key(
    *,
    project_id: str,
    normalized_question_hash: str,
    provider: str,
    model: str,
    document_id: str | None,
    use_parent_context: bool,
) -> str:
    dimensions = json.dumps(
        {
            "project_id": project_id,
            "question_hash": normalized_question_hash,
            "provider": provider,
            "model": model,
            "document_id": document_id,
            "use_parent_context": use_parent_context,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(dimensions.encode("utf-8")).hexdigest()
    return f"ragforge:query:v1:{digest}"


async def get_cached_query(key: str) -> dict[str, Any] | None:
    client = _client()
    if client is None:
        return None
    try:
        value = await client.get(key)
        return json.loads(value) if value else None
    except Exception:
        logger.warning("Redis query cache read failed", exc_info=True)
        return None


async def set_cached_query(key: str, value: dict[str, Any]) -> None:
    client = _client()
    if client is None or settings.QUERY_CACHE_TTL_SECONDS <= 0:
        return
    try:
        await client.setex(
            key,
            settings.QUERY_CACHE_TTL_SECONDS,
            json.dumps(value, separators=(",", ":")),
        )
    except Exception:
        logger.warning("Redis query cache write failed", exc_info=True)
