"""
NutriAgent Backend — Auth Routes.

POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DBSession
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenRefreshRequest,
    TokenResponse,
)
from app.services.auth_service import (
    authenticate_user,
    refresh_access_token,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(db: DBSession, data: RegisterRequest) -> TokenResponse:
    """Register a new user account."""
    user = await register_user(
        db, nickname=data.nickname, password=data.password,
        email=data.email, phone=data.phone, gender=data.gender,
    )
    identifier = data.email or data.phone or ""
    _, access_token, refresh_token, expires_in = await authenticate_user(
        db, identifier, data.password
    )
    return TokenResponse(
        access_token=access_token, refresh_token=refresh_token,
        token_type="bearer", expires_in=expires_in,
    )


@router.post("/login", response_model=TokenResponse)
async def login(db: DBSession, data: LoginRequest) -> TokenResponse:
    """Login with email/phone + password."""
    field, value = data.get_identifier()
    _, access_token, refresh_token, expires_in = await authenticate_user(
        db, value, data.password
    )
    return TokenResponse(
        access_token=access_token, refresh_token=refresh_token,
        token_type="bearer", expires_in=expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(db: DBSession, data: TokenRefreshRequest) -> TokenResponse:
    """
    Exchange a valid refresh token for a new token pair.
    Old refresh token is revoked (token rotation).
    """
    access_token, refresh_token, expires_in = await refresh_access_token(
        db, data.refresh_token
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
    )
