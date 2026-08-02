"""
NutriAgent Backend — Database Connection.

Supabase PostgreSQL + Vercel Serverless ready.
Async SQLAlchemy 2.0 with asyncpg driver.

Architecture:
  Local:   QueuePool (pool_size=5, max_overflow=5)
  Vercel:  NullPool (one connection per request, no leaks)
  SSL:     auto-detect — require on Supabase/Neon/Railway, prefer on localhost
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings

# ── ORM Base ──────────────────────────────────────────


class Base(DeclarativeBase):
    """Base for all ORM models. Models register via app.models.__init__."""


# ── Runtime Detection ─────────────────────────────────

_IS_SERVERLESS = bool(os.environ.get("VERCEL_DEPLOYMENT"))
_SUPABASE_HOST = "supabase" in settings.DATABASE_URL
_SSL_MODE = "require" if any(k in settings.DATABASE_URL for k in ("supabase", "neon", "railway")) else "prefer"


# ── Engine (created lazily on first query, no startup connect) ─

def _build_engine():
    """Build the async engine. Called once at module import — no actual DB connect yet."""
    common = {
        "echo": settings.DB_ECHO,
        "pool_pre_ping": True,  # verify connection alive before each use
        "connect_args": {
            "server_settings": {"application_name": f"{settings.APP_NAME.lower()}_backend"},
            "ssl": _SSL_MODE,
            "timeout": 10,
            "command_timeout": 30,
            "statement_cache_size": 0,  # Required for PgBouncer transaction mode (Supabase Pooler 6543)
        },
    }

    if _IS_SERVERLESS:
        # Vercel: each request gets its own connection, no pooling
        return create_async_engine(
            settings.DATABASE_URL,
            poolclass=NullPool,
            **common,
        )
    else:
        # Local/Server: small connection pool
        return create_async_engine(
            settings.DATABASE_URL,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            **common,
        )


engine = _build_engine()

# ── Session Factory ───────────────────────────────────

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# ── FastAPI Dependency ────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Per-request DB session. Commits on success, rolls back on error."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Agent / Script Session ────────────────────────────

@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Standalone session for agents/scripts. No auto-commit."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# ── Health Check ──────────────────────────────────────

async def check_db_health() -> bool:
    """Return True if database is reachable."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# ── Shutdown ──────────────────────────────────────────

async def dispose_engine() -> None:
    """Dispose the engine (call on app shutdown, local only)."""
    await engine.dispose()
