"""
NutriAgent Backend — Recommendation Context Builder.

Assembles enriched context for the RecommendationAgent:
- User location (city, district)
- Nearby healthy restaurants (from AMap + cache)
- Nutrition status (from dashboard)

Does NOT modify the agent — only enriches the request data.
"""

from __future__ import annotations

from uuid import UUID

from app.database import get_session
from app.models.user import UserHealthProfile
from app.services.restaurant_service import search_nearby_health_food
from sqlalchemy import select


async def build_location_context(user_id: UUID) -> dict:
    """
    Build location-enriched context for recommendation.

    Returns: {city, district, lat, lng, nearby_restaurants: [...]}
    Returns empty dict if no location data available.
    """
    async with get_session() as db:
        result = await db.execute(
            select(UserHealthProfile).where(UserHealthProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

    if not profile or not profile.latitude or not profile.longitude:
        return {}

    restaurants = await search_nearby_health_food(
        lat=float(profile.latitude),
        lng=float(profile.longitude),
        radius=3000,
        limit=10,
    )

    return {
        "city": profile.city or "",
        "district": profile.district or "",
        "province": profile.province or "",
        "latitude": float(profile.latitude),
        "longitude": float(profile.longitude),
        "nearby_restaurants": [
            {
                "name": r["name"],
                "distance": r["distance"],
                "health_score": r["health_score"],
            }
            for r in restaurants[:5]  # Top 5 for prompt context
        ],
    }
