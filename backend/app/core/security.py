"""
NutriAgent Backend — Security Utilities.

JWT token creation/verification, password hashing, and FastAPI auth dependencies.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config import settings

# --- Password Hashing ---


def hash_password(password: str) -> str:
    """Return bcrypt hash of a plaintext password."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if plaintext matches the bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


# --- JWT ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def create_access_token(user_id: str, *, extra_claims: dict | None = None) -> tuple[str, str]:
    """
    Create a JWT access token. Returns (token, jti).
    The jti can be used for refresh token management.
    """
    jti = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "jti": jti,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti


def create_refresh_token(user_id: str) -> tuple[str, str, datetime]:
    """
    Create a JWT refresh token. Returns (token, jti, expires_at).
    """
    jti = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "jti": jti,
        "type": "refresh",
        "iat": now,
        "exp": exp,
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti, exp


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT token. Returns the payload dict.
    Raises JWTError on any failure (expired, invalid signature, etc.).
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["sub", "exp", "jti", "type"]},
    )


# --- FastAPI Auth Dependency ---

async def get_current_user_id(
    token: str | None = Depends(oauth2_scheme),
) -> str:
    """
    FastAPI dependency: extract and verify the current user's ID from the JWT.
    Returns the user_id (UUID string) on success, raises 401 on failure.
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        user_id: str = payload["sub"]
        return user_id
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Optional auth — doesn't fail if no token is provided
async def get_optional_user_id(
    token: str | None = Depends(oauth2_scheme),
) -> str | None:
    """Like get_current_user_id, but returns None instead of 401 if unauthenticated."""
    if token is None:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return payload["sub"]
    except JWTError:
        return None
