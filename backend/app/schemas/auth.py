"""
NutriAgent Backend — Auth Schemas.

Pydantic models for authentication requests & responses.
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


# --- Request Schemas ---

class RegisterRequest(BaseModel):
    """User registration request."""

    nickname: str = Field(..., min_length=1, max_length=64, description="Display name")
    email: EmailStr | None = Field(None, description="Email (optional if using phone)")
    phone: str | None = Field(None, description="Phone number (optional if using email)")
    password: str = Field(..., min_length=8, max_length=128, description="Password, min 8 chars")
    gender: str | None = Field(None, description="male | female | other | prefer_not_to_say")


class LoginRequest(BaseModel):
    """Login request via email/phone + password."""

    email: EmailStr | None = Field(None)
    phone: str | None = Field(None)
    password: str = Field(..., min_length=1)

    def get_identifier(self) -> tuple[str, str]:
        """Return (field_name, value) for the login identifier."""
        if self.email:
            return "email", self.email
        if self.phone:
            return "phone", self.phone
        raise ValueError("Either email or phone must be provided")


class TokenRefreshRequest(BaseModel):
    """Request to refresh an expired access token."""

    refresh_token: str = Field(..., description="Valid refresh token")


# --- Response Schemas ---

class TokenResponse(BaseModel):
    """JWT token pair returned after login or refresh."""

    access_token: str = Field(..., description="JWT access token (short-lived)")
    refresh_token: str = Field(..., description="JWT refresh token (long-lived)")
    token_type: str = Field("bearer")
    expires_in: int = Field(..., description="Access token TTL in seconds")


class UserBriefResponse(BaseModel):
    """Minimal user info for auth responses."""

    id: str
    nickname: str
    email: str | None = None
    avatar_url: str | None = None
