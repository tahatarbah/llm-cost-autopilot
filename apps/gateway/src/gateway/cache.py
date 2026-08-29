from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import redis.asyncio as redis

from llm_shared.settings import settings

_redis: redis.Redis | None = None
_redis_failed = False
_memory: dict[str, tuple[float, str]] = {}


async def get_redis() -> redis.Redis | None:
    global _redis, _redis_failed
    if _redis_failed:
        return None
    if _redis is None:
        try:
            client = redis.from_url(settings.redis_url, decode_responses=True)
            await client.ping()
            _redis = client
        except Exception:
            _redis_failed = True
            return None
    return _redis


def cache_key(model: str, messages: list[dict[str, Any]], **kwargs: Any) -> str:
    payload = {"model": model, "messages": messages, **kwargs}
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return f"lca:cache:{digest}"


def _memory_get(key: str) -> dict[str, Any] | None:
    item = _memory.get(key)
    if not item:
        return None
    expires_at, raw = item
    if expires_at < time.time():
        _memory.pop(key, None)
        return None
    return json.loads(raw)


def _memory_set(key: str, value: dict[str, Any], ttl: int) -> None:
    _memory[key] = (time.time() + ttl, json.dumps(value))


async def cache_get(key: str) -> dict[str, Any] | None:
    client = await get_redis()
    if client is None:
        return _memory_get(key)
    try:
        raw = await client.get(key)
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        return _memory_get(key)


async def cache_set(key: str, value: dict[str, Any], ttl: int | None = None) -> None:
    ttl = ttl or settings.cache_ttl_seconds
    client = await get_redis()
    if client is None:
        _memory_set(key, value, ttl)
        return
    try:
        await client.set(key, json.dumps(value), ex=ttl)
    except Exception:
        _memory_set(key, value, ttl)
