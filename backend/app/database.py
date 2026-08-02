"""
NutriAgent Backend — Database Connection.

Provides async SQLAlchemy engine, session factory, and FastAPI dependency.
Uses asyncpg driver for PostgreSQL 16 with pgvector support.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# --- ORM Base ---
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models.

    Models must import this Base and subclass it.
    All models in app.models are registered via app.models.__init__.
    """


# --- Engine ---
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    connect_args={
        "server_settings": {
            "application_name": f"{settings.APP_NAME.lower()}_backend",
        },
    },
)

# --- Session Factory ---
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# --- FastAPI Dependency ---
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session. Rolls back on exception, closes after use."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# --- Utility: get a session for scripts / agents ---
@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# --- Health Check ---
async def check_db_health() -> bool:
    """Return True if the database is reachable."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# --- Shutdown ---
async def dispose_engine() -> None:
    """Dispose the database engine (call on app shutdown)."""
    await engine.dispose()
