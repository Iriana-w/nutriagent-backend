"""
NutriAgent Backend — Test Configuration & Fixtures.

Provides shared pytest fixtures for database sessions,
authenticated test clients, and test data factories.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.core.security import create_access_token, hash_password

# ============================================================================
# Test Database
# ============================================================================

TEST_DATABASE_URL = settings.DATABASE_URL.replace(
    "nutriagent", "nutriagent_test"
) if "nutriagent" in settings.DATABASE_URL else settings.DATABASE_URL + "_test"


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine — tables created once per session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test (rolled back after)."""
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        async with session.begin():
            yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(test_session) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP test client with the test DB session override."""

    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ============================================================================
# Auth Helpers
# ============================================================================


@pytest_asyncio.fixture
async def test_user(test_session) -> User:
    """Create a test user and return it."""
    user = User(
        id=uuid4(),
        nickname="TestUser",
        email="test@example.com",
        password_hash=hash_password("testpass123"),
        is_active=True,
    )
    test_session.add(user)
    await test_session.flush()
    await test_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user) -> dict[str, str]:
    """Generate Authorization headers for the test user."""
    token, _ = create_access_token(str(test_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_client(client, auth_headers) -> AsyncClient:
    """Return an authenticated async client."""
    client.headers.update(auth_headers)
    return client
