"""Best-effort Redis event replay with durable PostgreSQL recovery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import logging
from typing import Any

from app.core.config import settings


logger = logging.getLogger(__name__)
_redis = None

INGESTION_EVENT_TYPES = {
    "landed": "ingestion.landed",
    "queued": "ingestion.queued",
    "running": "ingestion.running",
    "silver_completed": "ingestion.chunking_completed",
    "gold_completed": "ingestion.embedding_completed",
    "indexed": "ingestion.completed",
    "failed": "ingestion.failed",
    "cancelled": "ingestion.cancelled",
}
INGESTION_STAGES = {
    "landed": "saving_original",
    "queued": "queued",
    "running": "parsing",
    "silver_completed": "chunking_completed",
    "gold_completed": "embedding_completed",
    "indexed": "completed",
    "failed": "failed",
    "cancelled": "cancelled",
}
INGESTION_SEQUENCE = {
    "landed": 1,
    "queued": 2,
    "running": 3,
    "silver_completed": 4,
    "gold_completed": 5,
    "indexed": 6,
    "failed": 7,
    "cancelled": 7,
}
TERMINAL_INGESTION_STATUSES = frozenset({"indexed", "failed", "cancelled"})
_NEXT_SEQUENCE_LUA = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
local floor = tonumber(ARGV[1])
local next_value = math.max(current + 1, floor)
redis.call('SET', KEYS[1], next_value)
return next_value
"""


@dataclass(frozen=True)
class StreamEvent:
    id: str
    event: str
    sequence: int
    data: dict[str, Any]
    timestamp: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event": self.event,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            **self.data,
        }


@dataclass(frozen=True)
class ReplayResult:
    events: list[StreamEvent]
    available: bool


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def format_sse(event: StreamEvent) -> str:
    payload = json.dumps(event.as_dict(), separators=(",", ":"), default=str)
    return f"id: {event.id}\nevent: {event.event}\ndata: {payload}\n\n"


def heartbeat_sse() -> str:
    return f": heartbeat {utc_timestamp()}\n\n"


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
            socket_timeout=1.0,
        )
    return _redis


def _stream_key(ingestion_run_id: str) -> str:
    return f"ragforge:events:ingestion:{ingestion_run_id}"


def _sequence_key(ingestion_run_id: str) -> str:
    return f"ragforge:events:ingestion:{ingestion_run_id}:sequence"


def durable_ingestion_event(
    ingestion_run_id: str,
    status: str,
    *,
    data: dict[str, Any] | None = None,
    snapshot: bool = False,
) -> StreamEvent:
    sequence = INGESTION_SEQUENCE.get(status, 0)
    event_type = "snapshot" if snapshot else INGESTION_EVENT_TYPES.get(status, "ingestion.updated")
    return StreamEvent(
        id=f"{'snapshot' if snapshot else 'durable'}-{sequence}-{status}",
        event=event_type,
        sequence=sequence,
        timestamp=utc_timestamp(),
        data={
            "ingestion_run_id": ingestion_run_id,
            "status": status,
            "stage": INGESTION_STAGES.get(status, status),
            "status_event": INGESTION_EVENT_TYPES.get(status, "ingestion.updated"),
            **(data or {}),
        },
    )


async def publish_ingestion_event(
    ingestion_run_id: str,
    status: str,
    *,
    data: dict[str, Any] | None = None,
) -> StreamEvent:
    """Publish an event for replay, degrading safely when Redis is unavailable."""
    client = _client()
    fallback = durable_ingestion_event(ingestion_run_id, status, data=data)
    if client is None:
        return fallback

    stream_key = _stream_key(ingestion_run_id)
    sequence_key = _sequence_key(ingestion_run_id)
    try:
        durable_floor = INGESTION_SEQUENCE.get(status, 0)
        sequence = int(
            await client.eval(
                _NEXT_SEQUENCE_LUA,
                1,
                sequence_key,
                durable_floor,
            )
        )
        fields = {
            "event": INGESTION_EVENT_TYPES.get(status, "ingestion.updated"),
            "sequence": str(sequence),
            "timestamp": utc_timestamp(),
            "data": json.dumps(
                {
                    "ingestion_run_id": ingestion_run_id,
                    "status": status,
                    "stage": INGESTION_STAGES.get(status, status),
                    **(data or {}),
                },
                separators=(",", ":"),
                default=str,
            ),
        }
        event_id = await client.xadd(
            stream_key,
            fields,
            maxlen=settings.EVENT_STREAM_MAXLEN,
            approximate=True,
        )
        await client.expire(stream_key, settings.EVENT_STREAM_TTL_SECONDS)
        await client.expire(sequence_key, settings.EVENT_STREAM_TTL_SECONDS)
        return StreamEvent(
            id=str(event_id),
            event=fields["event"],
            sequence=sequence,
            timestamp=fields["timestamp"],
            data=json.loads(fields["data"]),
        )
    except Exception:
        logger.warning("Redis ingestion event publish failed", exc_info=True)
        return fallback


def _parse_redis_event(event_id: str, fields: dict[str, str]) -> StreamEvent:
    return StreamEvent(
        id=str(event_id),
        event=fields["event"],
        sequence=int(fields["sequence"]),
        timestamp=fields["timestamp"],
        data=json.loads(fields["data"]),
    )


async def replay_ingestion_events(
    ingestion_run_id: str,
    after_id: str,
) -> ReplayResult:
    client = _client()
    if client is None or not after_id or "-" not in after_id or not after_id[0].isdigit():
        return ReplayResult(events=[], available=False)
    try:
        records = await client.xrange(
            _stream_key(ingestion_run_id),
            min=f"({after_id}",
            max="+",
            count=settings.EVENT_STREAM_MAXLEN,
        )
        return ReplayResult(
            events=[_parse_redis_event(event_id, fields) for event_id, fields in records],
            available=True,
        )
    except Exception:
        logger.warning("Redis ingestion event replay failed", exc_info=True)
        return ReplayResult(events=[], available=False)
