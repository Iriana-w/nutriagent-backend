"""
NutriAgent Backend — Delivery Routes.

GET  /api/v1/delivery/search
GET  /api/v1/delivery/merchants/{merchant_name}/menu
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUserId, DBSession
from app.schemas.food import DeliveryDishRead, DeliverySearchRequest
from app.services.delivery_service import get_delivery_menu_analysis, search_delivery_dishes

router = APIRouter(prefix="/delivery", tags=["Delivery"])


@router.post("/search", response_model=list[DeliveryDishRead])
async def search_delivery(
    db: DBSession,
    user_id: CurrentUserId,
    data: DeliverySearchRequest,
) -> list[DeliveryDishRead]:
    """
    Search nearby healthy delivery dishes.
    Filters by location, budget, health score, and keyword.
    """
    dishes = await search_delivery_dishes(
        db,
        lat=data.lat,
        lng=data.lng,
        radius_km=data.radius_km,
        query=data.query,
        budget_cent=data.budget_cent,
        min_health_score=data.min_health_score,
        limit=data.limit,
    )
    return [DeliveryDishRead.model_validate(d) for d in dishes]


@router.get("/merchants/{merchant_name}/menu", response_model=list[DeliveryDishRead])
async def get_merchant_menu(
    db: DBSession,
    user_id: CurrentUserId,
    merchant_name: str,
) -> list[DeliveryDishRead]:
    """
    Get a merchant's menu sorted by health score.
    Useful for choosing the healthiest option from a specific restaurant.
    """
    dishes = await get_delivery_menu_analysis(db, merchant_name)
    return [DeliveryDishRead.model_validate(d) for d in dishes]
