"""
NutriAgent Backend — Redis Client.

Upstash Redis + Serverless compatible.

Supports:
  - Upstash Redis  (redis:// or rediss://, auto-SSL)
  - Local Redis     (redis://localhost, no SSL)
  - Railway Redis   (REDIS_URL injected automatically)
  - No Redis        (all functions degrade gracefully, no crash)

Architecture:
  Single global client, created on first use.
  All business functions check `r is None` before calling.
  Serverless: small connection pool + health_check + keepalive.
"""

from __future__ import annotations

import json
import ssl
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.config import settings

# ── Global client ────────────────────────────────────

_redis: Redis | None = None
_redis_last_error: float = 0.0  # timestamp of last connection failure
_REDIS_RETRY_COOLDOWN: float = 30.0  # seconds before retrying after failure


def _detect_ssl(url: str) -> bool:
    """Auto-detect if SSL is needed."""
    url_lower = url.lower()
    return (
        url_lower.startswith("rediss://")
        or "upstash" in url_lower
        or ("6379" in url_lower and "localhost" not in url_lower and "127.0.0.1" not in url_lower)
    )


async def get_redis() -> Redis | None:
    """
    Return the Redis client, or None if unavailable.

    Serverless-safe:
      - Lazy connection on first use (not at import time)
      - Stale connection detection + auto-reconnect
      - Retry after cooldown (30s) on failure
      - Returns None gracefully if Redis is not configured
    """
    global _redis, _redis_last_error

    if not settings.REDIS_URL:
        return None

    # If we have a cached client, verify it's still alive
    if _redis is not None:
        try:
            await _redis.ping()
            return _redis
        except Exception:
            # Connection died (Upstash idle timeout, network blip, etc.)
            try:
                await _redis.close()
            except Exception:
                pass
            _redis = None
            # Fall through to create a new connection

    # Don't retry immediately after a failure — wait for cooldown
    import time
    now = time.time()
    if _redis_last_error > 0 and (now - _redis_last_error) < _REDIS_RETRY_COOLDOWN:
        return None

    # Create new connection
    try:
        url = settings.REDIS_URL

        if _detect_ssl(url):
            _redis = aioredis.from_url(
                url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=5,
                socket_keepalive=True,
                socket_connect_timeout=10,
                health_check_interval=30,
                ssl_cert_reqs=ssl.CERT_NONE,
            )
        else:
            _redis = aioredis.from_url(
                url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=5,
                socket_connect_timeout=5,
            )

        await _redis.ping()
        _redis_last_error = 0.0  # reset error timer on success
        return _redis

    except Exception:
        _redis = None
        _redis_last_error = time.time()
        return None


async def is_redis_available() -> bool:
    """Check if Redis is reachable."""
    r = await get_redis()
    if r is None:
        return False
    try:
        await r.ping()
        return True
    except Exception:
        return False


async def close_redis() -> None:
    """Close the Redis connection."""
    global _redis, _redis_last_error
    if _redis is not None:
        try:
            await _redis.close()
        except Exception:
            pass
        _redis = None
        _redis_last_error = 0.0


# ── Cache ───────────────────────────────────────────

async def cache_get(key: str) -> Any | None:
    r = await get_redis()
    if r is None:
        return None
    raw = await r.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    r = await get_redis()
    if r is None:
        return
    data = json.dumps(value, ensure_ascii=False, default=str)
    await r.setex(key, ttl, data)


async def cache_delete(key: str) -> None:
    r = await get_redis()
    if r is None:
        return
    await r.delete(key)


async def cache_delete_pattern(pattern: str) -> int:
    r = await get_redis()
    if r is None:
        return 0
    keys = await r.keys(pattern)
    if keys:
        return await r.delete(*keys)
    return 0


# ── Rate Limiting ───────────────────────────────────

async def check_rate_limit(
    user_id: str,
    endpoint: str,
    max_requests: int = 60,
    window_seconds: int = 60,
) -> bool:
    """Return True if request allowed. Always allow if Redis unavailable."""
    r = await get_redis()
    if r is None:
        return True
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


# ── JWT Refresh Token Store ─────────────────────────

async def store_refresh_token(user_id: str, jti: str, ttl_days: int = 30) -> None:
    r = await get_redis()
    if r is None:
        return
    key = f"refresh_token:{user_id}:{jti}"
    await r.setex(key, ttl_days * 86400, "1")


async def is_refresh_token_valid(user_id: str, jti: str) -> bool:
    """If Redis unavailable, assume token is valid (graceful degradation)."""
    r = await get_redis()
    if r is None:
        return True
    key = f"refresh_token:{user_id}:{jti}"
    return await r.exists(key) > 0


async def revoke_refresh_token(user_id: str, jti: str) -> None:
    r = await get_redis()
    if r is None:
        return
    key = f"refresh_token:{user_id}:{jti}"
    await r.delete(key)


async def revoke_all_refresh_tokens(user_id: str) -> int:
    r = await get_redis()
    if r is None:
        return 0
    return await cache_delete_pattern(f"refresh_token:{user_id}:*")
