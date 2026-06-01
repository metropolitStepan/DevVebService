from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings


redis_client: Redis | None = None
logger = logging.getLogger(__name__)

PURCHASE_CREATED_EVENT = "purchase.created"


async def init_redis() -> None:
    global redis_client

    client = Redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    try:
        await client.ping()
        redis_client = client
    except RedisError:
        await client.aclose()
        redis_client = None
        logger.warning("Redis is unavailable on startup. Running in degraded mode.")


async def close_redis() -> None:
    global redis_client

    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None


async def check_redis_health() -> bool:
    if redis_client is None:
        return False

    try:
        pong = await redis_client.ping()
        return bool(pong)
    except RedisError:
        return False


def build_redis_key(*parts: str) -> str:
    prefix = settings.redis_key_prefix.strip(":")
    if prefix:
        return ":".join([prefix, *parts])
    return ":".join(parts)


def purchase_reserve_key(*, user_id: int, idempotency_key: str) -> str:
    return build_redis_key("purchase", "reserve", str(user_id), idempotency_key)


def purchase_created_channel() -> str:
    return build_redis_key("events", PURCHASE_CREATED_EVENT)


async def acquire_purchase_reserve(
    *,
    user_id: int,
    idempotency_key: str,
    ttl_seconds: int,
) -> bool:
    if redis_client is None:
        return True

    key = purchase_reserve_key(user_id=user_id, idempotency_key=idempotency_key)
    try:
        locked = await redis_client.set(key, "1", ex=ttl_seconds, nx=True)
        return bool(locked)
    except RedisError:
        logger.warning(
            "Redis unavailable while creating purchase reserve. "
            "Continuing without reserve.",
        )
        return True


async def release_purchase_reserve(*, user_id: int, idempotency_key: str) -> None:
    if redis_client is None:
        return

    key = purchase_reserve_key(user_id=user_id, idempotency_key=idempotency_key)
    try:
        await redis_client.delete(key)
    except RedisError:
        logger.warning("Redis unavailable while removing purchase reserve.")


async def publish_purchase_created(payload: dict[str, Any]) -> bool:
    if redis_client is None:
        return False

    envelope = {
        "event_id": str(uuid4()),
        "event_name": PURCHASE_CREATED_EVENT,
        "occurred_at": datetime.now(UTC).isoformat(),
        "payload": payload,
    }
    try:
        message = json.dumps(envelope, default=_json_serializer, separators=(",", ":"))
        await redis_client.publish(channel=purchase_created_channel(), message=message)
        return True
    except (RedisError, TypeError, ValueError):
        logger.warning("Failed to publish purchase.created event to Redis.")
        return False


def _json_serializer(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")
