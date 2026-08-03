"""
NutriAgent Backend — Location Routes.

POST /api/v1/location/update
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import CurrentUserId, DBSession
from app.config import settings
from app.services.location_service import reverse_geocode
from app.services.user_service import get_or_create_health_profile

router = APIRouter(prefix="/location", tags=["Location"])


@router.get("/current")
async def get_current_location(
    db: DBSession,
    user_id: CurrentUserId,
) -> dict:
    """Get current user's saved location."""
    profile = await get_or_create_health_profile(db, UUID(user_id))
    return {
        "latitude": float(profile.latitude) if profile.latitude else None,
        "longitude": float(profile.longitude) if profile.longitude else None,
        "city": profile.city,
        "district": profile.district,
        "province": profile.province,
        "location_source": profile.location_source or "gps",
    }


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


@router.get("/cities/search")
async def search_cities(q: str = Query(..., min_length=1)):
    """Search cities for manual selection."""
    import httpx
    try:
        r = await httpx.AsyncClient(timeout=10.0, trust_env=False).get(
            "https://restapi.amap.com/v3/config/district",
            params={"key": settings.AMAP_API_KEY, "keywords": q, "subdistrict": 0, "offset": 10, "output": "json"},
        )
        r.raise_for_status()
        d = r.json()
        cities = []
        if d.get("status") == "1" and d.get("districts"):
            for dist in d["districts"][:10]:
                c = dist.get("center", "0,0").split(",")
                cities.append({
                    "name": dist.get("name", ""), "adcode": dist.get("adcode", ""),
                    "province": dist.get("name", ""),
                    "center": {"lng": float(c[0]) if len(c)>0 else 0, "lat": float(c[1]) if len(c)>1 else 0},
                })
        return {"query": q, "cities": cities}
    except Exception:
        return {"query": q, "cities": []}


class ManualLocationRequest(BaseModel):
    city: str
    province: str = ""
    adcode: str = ""


@router.post("/manual", response_model=LocationResponse)
async def set_manual_location(
    db: DBSession,
    user_id: CurrentUserId,
    data: ManualLocationRequest,
) -> LocationResponse:
    """Manually set city location."""
    try:
        profile = await get_or_create_health_profile(db, UUID(user_id))

        # Get city center from AMap district API
        import httpx
        try:
            r = await httpx.AsyncClient(timeout=10.0, trust_env=False).get(
                "https://restapi.amap.com/v3/config/district",
                params={"key": settings.AMAP_API_KEY, "keywords": data.adcode or data.city, "subdistrict": 0, "output": "json"},
            )
            r.raise_for_status()
            d = r.json()
            if d.get("status") == "1" and d.get("districts"):
                center_str = d["districts"][0].get("center", "0,0")
                parts = center_str.split(",")
                if len(parts) == 2:
                    profile.latitude = float(parts[1])
                    profile.longitude = float(parts[0])
        except Exception:
            pass

        profile.city = data.city
        profile.province = data.province
        profile.location_source = "manual"
        profile.location_updated_at = datetime.now(timezone.utc)

        await db.flush()
        await db.refresh(profile)

        return LocationResponse(
            latitude=float(profile.latitude) if profile.latitude else 0,
            longitude=float(profile.longitude) if profile.longitude else 0,
            city=profile.city, district=profile.district, province=profile.province,
            updated_at=profile.location_updated_at.isoformat() if profile.location_updated_at else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)[:300]}")


@router.post("/update", response_model=LocationResponse)
async def update_location(
    db: DBSession,
    user_id: CurrentUserId,
    data: LocationUpdateRequest,
) -> LocationResponse:
    """Update user location with reverse geocoding."""
    try:
        geo = await reverse_geocode(data.latitude, data.longitude)
        profile = await get_or_create_health_profile(db, UUID(user_id))

        profile.latitude = data.latitude
        profile.longitude = data.longitude
        profile.location_source = "gps"
        profile.location_updated_at = datetime.now(timezone.utc)

        # Only update if AMAP returned valid data (don't overwrite with None)
        if geo.get("city"):     profile.city = geo["city"]
        if geo.get("district"): profile.district = geo["district"]
        if geo.get("province"): profile.province = geo["province"]

        await db.flush()
        await db.refresh(profile)

        return LocationResponse(
            latitude=data.latitude, longitude=data.longitude,
            city=profile.city, district=profile.district, province=profile.province,
            updated_at=profile.location_updated_at.isoformat() if profile.location_updated_at else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)[:300]}")
