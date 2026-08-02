"""
NutriAgent Backend — Redis Client.

Provides async Redis connection for caching, session storage,
rate limiting, and task queue brokering.
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.config import settings

# --- Global Redis instance ---
_redis: Redis | None = None


async def get_redis() -> Redis:
    """Return the global async Redis client, creating it if needed."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            password=settings.REDIS_PASSWORD or None,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis


async def close_redis() -> None:
    """Close the Redis connection (call on app shutdown)."""
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None


# --- Cache Helpers ---

async def cache_get(key: str) -> Any | None:
    """Get a cached value as parsed JSON, or None on miss."""
    r = await get_redis()
    raw = await r.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


async def cache_set(
    key: str,
    value: Any,
    ttl: int = 300,  # default 5 minutes
) -> None:
    """Set a cache key with JSON-serialized value and TTL in seconds."""
    r = await get_redis()
    data = json.dumps(value, ensure_ascii=False, default=str)
    await r.setex(key, ttl, data)


async def cache_delete(key: str) -> None:
    """Delete a cache key."""
    r = await get_redis()
    await r.delete(key)


async def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching a glob pattern. Returns count deleted."""
    r = await get_redis()
    keys = await r.keys(pattern)
    if keys:
        return await r.delete(*keys)
    return 0


# --- Rate Limiting (simple sliding-window counter) ---

async def check_rate_limit(
    user_id: str,
    endpoint: str,
    max_requests: int = 60,
    window_seconds: int = 60,
) -> bool:
    """
    Return True if the request is allowed, False if rate-limited.
    Uses a simple per-endpoint counter with TTL.
    """
    r = await get_redis()
    key = f"rate_limit:{endpoint}:{user_id}"
    current = await r.get(key)

    if current is None:
        await r.setex(key, window_seconds, 1)
        return True

    count = int(current)
    if count >= max_requests:
        return False

    ttl = await r.ttl(key)
    if ttl < 0:
        ttl = window_seconds
    await r.setex(key, ttl, count + 1)
    return True


# --- JWT Refresh Token Storage ---

async def store_refresh_token(user_id: str, jti: str, ttl_days: int = 30) -> None:
    """Store a refresh token JTI in Redis."""
    r = await get_redis()
    key = f"refresh_token:{user_id}:{jti}"
    await r.setex(key, ttl_days * 86400, "1")


async def is_refresh_token_valid(user_id: str, jti: str) -> bool:
    """Check if a refresh token JTI is still valid (exists in Redis)."""
    r = await get_redis()
    key = f"refresh_token:{user_id}:{jti}"
    return await r.exists(key) > 0


async def revoke_refresh_token(user_id: str, jti: str) -> None:
    """Revoke a specific refresh token."""
    r = await get_redis()
    key = f"refresh_token:{user_id}:{jti}"
    await r.delete(key)


async def revoke_all_refresh_tokens(user_id: str) -> int:
    """Revoke all refresh tokens for a user. Returns count revoked."""
    return await cache_delete_pattern(f"refresh_token:{user_id}:*")
