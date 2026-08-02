"""
NutriAgent Backend — Common Schemas.

Shared Pydantic models for pagination, error responses, etc.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    items: list[T] = Field(default_factory=list)
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    pages: int = Field(..., description="Total number of pages")

    @classmethod
    def from_items(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedResponse[T]":
        pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str = Field(..., description="Error type / class name")
    message: str = Field(..., description="Human-readable error message")
    detail: dict[str, Any] = Field(default_factory=dict, description="Additional error details")


class SuccessResponse(BaseModel):
    """Generic success message."""

    message: str = Field("ok")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    database: str
