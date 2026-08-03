"""
NutriAgent Backend — Restaurant Routes.

GET /api/v1/restaurants/nearby
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.restaurant_service import search_nearby_health_food

router = APIRouter(prefix="/restaurants", tags=["Restaurants"])


@router.get("/nearby")
async def get_nearby_restaurants(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius: int = Query(3000, ge=500, le=10000, description="Search radius in meters"),
) -> dict:
    """
    Search nearby healthy restaurants/food.

    Tries Redis cache first (TTL 5 min), falls back to AMap POI search.
    Each result includes a health score (0-100).
    """
    restaurants = await search_nearby_health_food(
        lat=latitude, lng=longitude, radius=radius,
    )
    return {
        "latitude": latitude,
        "longitude": longitude,
        "radius": radius,
        "count": len(restaurants),
        "restaurants": restaurants,
    }
