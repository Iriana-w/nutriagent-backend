"""
NutriAgent Backend — Delivery Service.

Handles delivery dish search and menu health analysis.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food import DeliveryDish


async def search_delivery_dishes(
    db: AsyncSession,
    *,
    lat: float,
    lng: float,
    radius_km: float = 3.0,
    query: str = "",
    budget_cent: int | None = None,
    min_health_score: int = 50,
    limit: int = 20,
) -> list[DeliveryDish]:
    """
    Search nearby delivery dishes using geographic filtering.
    Uses the Haversine formula for distance calculation.
    """
    conditions = [DeliveryDish.health_score >= min_health_score]

    if budget_cent is not None:
        conditions.append(DeliveryDish.price_cent <= budget_cent)

    if query:
        conditions.append(DeliveryDish.dish_name.ilike(f"%{query}%"))

    # Distance filter (approx — precise Haversine via raw SQL)
    # Filter: dishes within radius_km
    distance_expr = text(
        """
        6371 * acos(
            cos(radians(:lat)) * cos(radians(merchant_lat))
            * cos(radians(merchant_lng) - radians(:lng))
            + sin(radians(:lat)) * sin(radians(merchant_lat))
        )
        """
    ).bindparams(lat=lat, lng=lng)

    stmt = (
        select(DeliveryDish)
        .where(and_(*conditions))
        .where(distance_expr <= radius_km)
        .order_by(DeliveryDish.health_score.desc(), DeliveryDish.price_cent.asc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_delivery_menu_analysis(
    db: AsyncSession,
    merchant_name: str,
) -> list[DeliveryDish]:
    """
    Get a merchant's full menu sorted by health score.
    Useful for analyzing which dishes at a restaurant are healthiest.
    """
    stmt = (
        select(DeliveryDish)
        .where(DeliveryDish.merchant_name.ilike(f"%{merchant_name}%"))
        .order_by(DeliveryDish.health_score.desc())
        .limit(50)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
