"""
NutriAgent Backend — Shared API Dependencies.

FastAPI dependency injection for database sessions, authentication,
rate limiting, and pagination.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user_id
from app.database import get_db

# --- Database ---
DBSession = Annotated[AsyncSession, Depends(get_db)]

# --- Auth ---
CurrentUserId = Annotated[str, Depends(get_current_user_id)]


# --- Pagination ---
async def pagination_params(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> dict:
    return {"page": page, "page_size": page_size}


Pagination = Annotated[dict, Depends(pagination_params)]
