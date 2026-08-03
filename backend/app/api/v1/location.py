"""
NutriAgent Backend — Location Routes.

POST /api/v1/location/update
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentUserId, DBSession
from app.services.location_service import reverse_geocode
from app.services.user_service import get_or_create_health_profile

router = APIRouter(prefix="/location", tags=["Location"])


class LocationUpdateRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class LocationResponse(BaseModel):
    latitude: float
    longitude: float
    city: str | None = None
    district: str | None = None
    province: str | None = None
    updated_at: str | None = None


@router.post("/update", response_model=LocationResponse)
async def update_location(
    db: DBSession,
    user_id: CurrentUserId,
    data: LocationUpdateRequest,
) -> LocationResponse:
    """
    Update user location. Reverse geocodes lat/lng to city/district/province.
    Stores result in user_health_profiles.
    """
    # Reverse geocode
    geo = await reverse_geocode(data.latitude, data.longitude)

    # Get or create profile
    profile = await get_or_create_health_profile(db, UUID(user_id))

    # Update
    profile.latitude = data.latitude
    profile.longitude = data.longitude
    profile.city = geo.get("city")
    profile.district = geo.get("district")
    profile.province = geo.get("province")
    profile.location_updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(profile)

    return LocationResponse(
        latitude=data.latitude,
        longitude=data.longitude,
        city=profile.city,
        district=profile.district,
        province=profile.province,
        updated_at=profile.location_updated_at.isoformat() if profile.location_updated_at else None,
    )
