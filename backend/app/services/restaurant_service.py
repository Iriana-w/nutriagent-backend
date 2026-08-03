"""
NutriAgent Backend — Restaurant Service.

Nearby healthy food search with health scoring + Redis caching.
"""

from __future__ import annotations

import json

from app.redis import cache_get, cache_set
from app.services.amap_client import amap_client
from app.services.restaurant_health import calculate_health_score

HEALTH_KEYWORDS = ["轻食", "健身餐", "沙拉", "低脂餐", "营养餐", "素食", "健康餐"]


async def search_nearby_health_food(
    lat: float,
    lng: float,
    radius: int = 3000,
    limit: int = 20,
) -> list[dict]:
    """
    Search nearby healthy restaurants with health scoring.

    Cache key: nearby_food:{lat}:{lng}:{radius}, TTL 300s.
    """
    # Round coords for cache key (3 decimal = ~100m precision)
    cache_key = f"nearby_food:{lat:.3f}:{lng:.3f}:{radius}"

    # Try cache
    cached = await cache_get(cache_key)
    if cached and isinstance(cached, list):
        return cached[:limit]

    # Search via AMap
    results = []
    seen = set()

    for keyword in HEALTH_KEYWORDS:
        pois = await amap_client.poi_search(
            keyword=keyword, lat=lat, lng=lng, radius=radius, limit=10,
        )
        for p in pois:
            name = p["name"]
            if name not in seen:
                seen.add(name)
                results.append({
                    "name": name,
                    "address": p.get("address", ""),
                    "distance": p.get("distance", 0),
                    "health_score": calculate_health_score(name, p.get("type", "")),
                })

    # Sort by health_score desc, then distance asc
    results.sort(key=lambda x: (-x["health_score"], x["distance"]))
    results = results[:limit]

    # Cache for 5 minutes
    if results:
        await cache_set(cache_key, results, ttl=300)

    return results
