"""
NutriAgent Backend — Auth Tests.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Verify the health check endpoint responds."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    """Test user registration."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "nickname": "NewUser",
            "email": "newuser@example.com",
            "password": "securepass123",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Test that duplicate email registration fails."""
    # First registration
    await client.post(
        "/api/v1/auth/register",
        json={
            "nickname": "User1",
            "email": "dup@example.com",
            "password": "pass123456",
        },
    )
    # Duplicate
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "nickname": "User2",
            "email": "dup@example.com",
            "password": "pass123456",
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    """Test login with registered credentials."""
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={
            "nickname": "LoginUser",
            "email": "login@example.com",
            "password": "mypassword123",
        },
    )
    # Login
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "mypassword123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """Test login with wrong password fails."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "nickname": "FailUser",
            "email": "fail@example.com",
            "password": "correctpass123",
        },
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "fail@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_no_auth(client: AsyncClient):
    """Test that protected endpoints require authentication."""
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401
