"""
app/infrastructure/cache/redis_client.py
Async Redis client with graceful fallback for resilience.
"""
from __future__ import annotations
import json
from typing import Any
import redis.asyncio as aioredis
from app.config.settings import get_settings
from app.observability.logging import get_logger

logger = get_logger(__name__)

_redis_client: aioredis.Redis | None = None
_redis_checked: bool = False


import socket
from urllib.parse import urlparse


def _probe_redis(url: str, timeout: float = 0.05) -> bool:
    try:
        p = urlparse(url)
        host = p.hostname or "127.0.0.1"
        port = p.port or 6379
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


async def get_redis_client() -> aioredis.Redis | None:
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client

    _redis_checked = True
    settings = get_settings()

    if not _probe_redis(settings.redis_url):
        logger.info("redis_not_available_using_in_memory_fallback")
        _redis_client = None
        return None

    try:
        client = aioredis.from_url(
            settings.redis_url,
            max_connections=settings.redis_max_connections,
            decode_responses=True,
            socket_timeout=0.5,
        )
        await client.ping()
        _redis_client = client
        logger.info("redis_connected", url=settings.redis_url)
    except Exception as exc:
        logger.warning("redis_unavailable_fallback_active", error=str(exc))
        _redis_client = None

    return _redis_client


async def close_redis_client() -> None:
    global _redis_client
    if _redis_client is not None:
        logger.info("closing_redis_client")
        await _redis_client.aclose()
        _redis_client = None


async def set_json(key: str, value: Any, ttl_seconds: int = 3600) -> bool:
    client = await get_redis_client()
    if not client:
        return False
    try:
        data = json.dumps(value)
        await client.set(key, data, ex=ttl_seconds)
        return True
    except Exception as exc:
        logger.warning("redis_set_failed", key=key, error=str(exc))
        return False


async def get_json(key: str) -> Any | None:
    client = await get_redis_client()
    if not client:
        return None
    try:
        val = await client.get(key)
        if val is None:
            return None
        return json.loads(val)
    except Exception as exc:
        logger.warning("redis_get_failed", key=key, error=str(exc))
        return None
