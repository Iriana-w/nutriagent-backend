"""
NutriAgent Backend — Location Service.

Reverse geocode lat/lng → city/district/province via AMap API.
"""

from __future__ import annotations

import httpx
from app.config import settings


AMAP_GEO_URL = "https://restapi.amap.com/v3/geocode/regeo"


async def reverse_geocode(lat: float, lng: float) -> dict:
    """
    Call AMap reverse geocoding API.
    Returns {city, district, province, adcode} or empty dict on failure.
    """
    api_key = settings.AMAP_API_KEY
    if not api_key:
        return {}

    try:
        async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
            r = await client.get(
                AMAP_GEO_URL,
                params={
                    "key": api_key,
                    "location": f"{lng},{lat}",
                    "output": "json",
                },
            )
            r.raise_for_status()
            data = r.json()

            if data.get("status") != "1" or not data.get("regeocode"):
                return {}

            addr = data["regeocode"].get("addressComponent", {})

            def _s(val):
                """Coerce AMap response to string (handles empty arrays)."""
                return val if isinstance(val, str) else ""

            return {
                "province": _s(addr.get("province", "")),
                "city": _s(addr.get("city", addr.get("province", ""))),
                "district": _s(addr.get("district", "")),
            }
    except Exception:
        return {}
