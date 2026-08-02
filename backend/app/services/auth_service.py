"""
NutriAgent Backend — Auth Service.

Handles user registration, login, token refresh, and password management.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.redis import (
    is_refresh_token_valid,
    revoke_refresh_token,
    store_refresh_token,
)


async def register_user(
    db: AsyncSession,
    *,
    nickname: str,
    password: str,
    email: str | None = None,
    phone: str | None = None,
    gender: str | None = None,
) -> User:
    """Register a new user. Raises ConflictError on duplicate email/phone."""
    # Check for duplicates
    if email:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise ConflictError(f"Email '{email}' is already registered")
    if phone:
        existing = await db.execute(select(User).where(User.phone == phone))
        if existing.scalar_one_or_none():
            raise ConflictError(f"Phone '{phone}' is already registered")

    user = User(
        nickname=nickname,
        email=email,
        phone=phone,
        gender=gender,
        password_hash=hash_password(password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def authenticate_user(
    db: AsyncSession,
    identifier: str,
    password: str,
) -> tuple[User, str, str, int]:
    """
    Authenticate a user by email/phone + password.
    Returns (user, access_token, refresh_token, expires_in_seconds).
    Raises AuthenticationError on failure.
    """
    # Find user by email or phone
    stmt = select(User).where(
        (User.email == identifier) | (User.phone == identifier)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not user.password_hash:
        raise AuthenticationError("Invalid credentials")
    if not user.is_active:
        raise AuthenticationError("Account is deactivated")
    if not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid credentials")

    # Generate tokens
    access_token, _ = create_access_token(str(user.id))
    refresh_token, jti, _exp = create_refresh_token(str(user.id))

    # Store refresh token in Redis
    await store_refresh_token(str(user.id), jti, settings.REFRESH_TOKEN_EXPIRE_DAYS)

    return user, access_token, refresh_token, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


async def refresh_access_token(
    db: AsyncSession,
    refresh_token: str,
) -> tuple[str, str, int]:
    """
    Validate refresh token and issue a new token pair.
    Returns (new_access_token, new_refresh_token, expires_in_seconds).
    Raises AuthenticationError on invalid/expired/revoked token.
    """
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid token type")
    except Exception:
        raise AuthenticationError("Invalid or expired refresh token")

    user_id = payload["sub"]
    jti = payload["jti"]

    # Verify token is still valid in Redis
    if not await is_refresh_token_valid(user_id, jti):
        raise AuthenticationError("Refresh token has been revoked")

    # Verify user still exists and is active
    result = await db.execute(
        select(User).where(User.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise AuthenticationError("Account not found or deactivated")

    # Revoke old refresh token (rotation)
    await revoke_refresh_token(user_id, jti)

    # Issue new pair
    new_access_token, _ = create_access_token(user_id)
    new_refresh_token, new_jti, _exp = create_refresh_token(user_id)
    await store_refresh_token(user_id, new_jti, settings.REFRESH_TOKEN_EXPIRE_DAYS)

    return new_access_token, new_refresh_token, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


async def get_user_by_id(db: AsyncSession, user_id: str) -> User:
    """Fetch a user by UUID string. Raises NotFoundError if missing."""
    result = await db.execute(
        select(User).where(User.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User", user_id)
    return user
