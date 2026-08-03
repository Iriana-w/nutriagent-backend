"""
NutriAgent Backend — Location Service.

Thin wrapper around AmapClient.reverse_geocode().
"""

from __future__ import annotations

from app.services.amap_client import amap_client


async def reverse_geocode(lat: float, lng: float) -> dict:
    """Reverse geocode lat/lng → {province, city, district, ...} via AMap."""
    return await amap_client.reverse_geocode(lat, lng)
