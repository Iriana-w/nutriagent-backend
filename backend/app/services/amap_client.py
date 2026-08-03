"""
NutriAgent Backend — AMap (高德) Web Service API Client.

Unified client for:
- reverse_geocode: lat/lng → address
- poi_search: nearby POI search by keyword

Docs: https://lbs.amap.com/api/webservice/summary
"""

from __future__ import annotations

from typing import Any

import httpx
from app.config import settings


GEOCODE_URL = "https://restapi.amap.com/v3/geocode/regeo"
POI_URL = "https://restapi.amap.com/v3/place/around"
DISTRICT_URL = "https://restapi.amap.com/v3/config/district"


class AmapClient:
    """Unified AMap Web Service API client."""

    def __init__(self):
        self._key = settings.AMAP_API_KEY

    @property
    def key(self) -> str:
        return self._key

    # ── Reverse Geocode ─────────────────────────

    async def reverse_geocode(self, lat: float, lng: float) -> dict[str, str]:
        """
        lat/lng → address components.

        Returns: {province, city, district, township, formatted_address}
        On failure: returns empty dict.
        """
        if not self.key:
            return {}

        try:
            async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
                r = await client.get(
                    GEOCODE_URL,
                    params={
                        "key": self.key,
                        "location": f"{lng},{lat}",
                        "output": "json",
                    },
                )
                r.raise_for_status()
                data = r.json()

                if data.get("status") != "1" or not data.get("regeocode"):
                    return {}

                addr = data["regeocode"].get("addressComponent", {})
                return {
                    "province": _s(addr.get("province", "")),
                    "city": _s(addr.get("city", addr.get("province", ""))),
                    "district": _s(addr.get("district", "")),
                    "township": _s(addr.get("township", "")),
                    "formatted_address": str(data["regeocode"].get("formatted_address", "")),
                }
        except Exception:
            return {}

    # ── POI Search ─────────────────────────────

    async def poi_search(
        self,
        keyword: str,
        lat: float,
        lng: float,
        radius: int = 3000,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Search nearby POIs by keyword.

        Returns: [{name, address, type, distance, location: {lat, lng}}]
        On failure: returns empty list.
        """
        if not self.key:
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
                r = await client.get(
                    POI_URL,
                    params={
                        "key": self.key,
                        "keywords": keyword,
                        "location": f"{lng},{lat}",
                        "radius": radius,
                        "offset": limit,
                        "output": "json",
                        "extensions": "base",
                    },
                )
                r.raise_for_status()
                data = r.json()

                if data.get("status") != "1" or not data.get("pois"):
                    return []

                return [
                    {
                        "name": p.get("name", ""),
                        "address": p.get("address", ""),
                        "type": p.get("type", ""),
                        "distance": int(p.get("distance", 0)),
                        "location": {
                            "lat": float(p.get("location", "").split(",")[1]) if p.get("location") else 0,
                            "lng": float(p.get("location", "").split(",")[0]) if p.get("location") else 0,
                        },
                    }
                    for p in data["pois"][:limit]
                ]
        except Exception:
            return []


def _s(val: Any) -> str:
    """Coerce AMap response value to string (handles empty arrays [])."""
    if isinstance(val, str):
        return val
    return ""


    # ── City Search ────────────────────────────

    async def search_cities(self, keyword: str, limit: int = 10) -> list[dict]:
        """
        Search cities/districts by keyword.

        Returns: [{name, city, province, adcode, center: {lat, lng}}]
        """
        if not self.key or len(keyword) < 1:
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
                r = await client.get(
                    DISTRICT_URL,
                    params={
                        "key": self.key,
                        "keywords": keyword,
                        "subdistrict": 0,
                        "offset": limit,
                        "output": "json",
                    },
                )
                r.raise_for_status()
                data = r.json()

                if data.get("status") != "1" or not data.get("districts"):
                    return []

                results = []
                for d in data["districts"][:limit]:
                    center = d.get("center", "0,0").split(",")
                    results.append({
                        "name": d.get("name", ""),
                        "city": d.get("name", ""),
                        "province": d.get("name", ""),
                        "adcode": d.get("adcode", ""),
                        "center": {
                            "lng": float(center[0]) if len(center) > 0 else 0,
                            "lat": float(center[1]) if len(center) > 1 else 0,
                        },
                    })
                return results
        except Exception:
            return []

    async def get_city_center(self, adcode: str) -> dict | None:
        """Get city center coordinates by adcode."""
        results = await self.search_cities(adcode, limit=1)
        return results[0] if results else None


# Module-level singleton
amap_client = AmapClient()
