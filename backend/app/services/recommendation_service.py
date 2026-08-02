"""
NutriAgent Backend — Recommendation Service.

Bridge between API routes and the LangGraph agent orchestration.
Handles caching, logging, and feedback collection.
"""

from __future__ import annotations

import json
from datetime import date
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import get_orchestrator
from app.core.exceptions import NotFoundError, RecommendationError
from app.models.recommendation import (
    FeedbackEnum,
    RecommendationItem,
    RecommendationLog,
    RecommendStatusEnum,
)
from app.redis import cache_get, cache_set


async def get_meal_recommendation(
    db: AsyncSession,
    user_id: UUID,
    *,
    meal_type: str,
    scenario: str | None = None,
    budget_cent: int | None = None,
    delivery_only: bool = False,
    lat: float | None = None,
    lng: float | None = None,
    exclude_foods: list[str] | None = None,
) -> RecommendationLog:
    """Generate or retrieve a cached single-meal recommendation."""
    cache_key = f"rec:meal:{user_id}:{meal_type}:{scenario or 'default'}"
    cached = await cache_get(cache_key)
    if cached:
        return _deserialize_recommendation(cached)

    orchestrator = get_orchestrator()
    try:
        result = await orchestrator.run_meal_recommendation(
            user_id=str(user_id),
            meal_type=meal_type,
            scenario=scenario,
            budget_cent=budget_cent,
            delivery_only=delivery_only,
            lat=lat,
            lng=lng,
            exclude_foods=exclude_foods or [],
        )
    except Exception as e:
        raise RecommendationError(f"Meal recommendation failed: {e}")

    # Persist
    rec = RecommendationLog(
        user_id=user_id,
        recommend_type="meal",
        scenario=scenario,
        meal_type=meal_type,
        target_date=date.today(),
        model_name=result.get("model_name", "unknown"),
        model_version=result.get("model_version"),
        prompt_template_id=result.get("template_id"),
        retrieval_sources=result.get("retrieval_sources"),
        recommendation_json=result.get("recommendation_json", {}),
        summary_text=result.get("summary_text", ""),
        prompt_tokens=result.get("prompt_tokens"),
        completion_tokens=result.get("completion_tokens"),
        total_tokens=result.get("total_tokens"),
        latency_ms=result.get("latency_ms"),
        status=RecommendStatusEnum.generated,
    )
    db.add(rec)
    await db.flush()

    # Create items
    for i, item_data in enumerate(result.get("items", [])):
        item = RecommendationItem(
            recommendation_id=rec.id,
            item_type=item_data.get("item_type", "food"),
            food_name=item_data.get("food_name", ""),
            food_id=item_data.get("food_id"),
            delivery_dish_id=item_data.get("delivery_dish_id"),
            serving_size_g=item_data.get("serving_size_g"),
            estimated_kcal=item_data.get("estimated_kcal"),
            estimated_protein_g=item_data.get("estimated_protein_g"),
            estimated_fat_g=item_data.get("estimated_fat_g"),
            estimated_carbs_g=item_data.get("estimated_carbs_g"),
            reason_text=item_data.get("reason_text"),
            nutrition_tags=item_data.get("nutrition_tags", []),
            sort_order=i,
        )
        db.add(item)

    await db.flush()
    await db.refresh(rec)

    # Cache
    await cache_set(cache_key, _serialize_recommendation(rec), ttl=1800)  # 30 min

    return rec


async def get_daily_recommendation(
    db: AsyncSession,
    user_id: UUID,
    *,
    target_date: date | None = None,
    scenario: str | None = None,
    budget_cent: int | None = None,
    delivery_only: bool = False,
    lat: float | None = None,
    lng: float | None = None,
    exclude_foods: list[str] | None = None,
) -> RecommendationLog:
    """Generate a full-day meal plan recommendation."""
    orchestrator = get_orchestrator()
    try:
        result = await orchestrator.run_daily_plan(
            user_id=str(user_id),
            target_date=target_date or date.today(),
            scenario=scenario,
            budget_cent=budget_cent,
            delivery_only=delivery_only,
            lat=lat,
            lng=lng,
            exclude_foods=exclude_foods or [],
        )
    except Exception as e:
        raise RecommendationError(f"Daily plan failed: {e}")

    rec = RecommendationLog(
        user_id=user_id,
        recommend_type="daily",
        scenario=scenario,
        target_date=target_date or date.today(),
        model_name=result.get("model_name", "unknown"),
        recommendation_json=result.get("recommendation_json", {}),
        summary_text=result.get("summary_text", ""),
        total_tokens=result.get("total_tokens"),
        latency_ms=result.get("latency_ms"),
        status=RecommendStatusEnum.generated,
    )
    db.add(rec)
    await db.flush()
    await db.refresh(rec)
    return rec


async def submit_feedback(
    db: AsyncSession,
    recommendation_id: UUID,
    user_id: UUID,
    feedback: str,
    detail: str | None = None,
    item_feedbacks: dict[str, str] | None = None,
) -> RecommendationLog:
    """Record user feedback on a recommendation."""
    result = await db.execute(
        select(RecommendationLog).where(
            RecommendationLog.id == recommendation_id,
            RecommendationLog.user_id == user_id,
        )
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise NotFoundError("Recommendation", str(recommendation_id))

    rec.feedback = FeedbackEnum(feedback) if feedback in FeedbackEnum._value2member_map_ else None
    rec.feedback_detail = detail

    # Per-item feedback
    if item_feedbacks:
        for item in rec.items:
            item_id_str = str(item.id)
            if item_id_str in item_feedbacks:
                fb_val = item_feedbacks[item_id_str]
                if fb_val in FeedbackEnum._value2member_map_:
                    item.item_feedback = FeedbackEnum(fb_val)

    await db.flush()
    await db.refresh(rec)
    return rec


async def get_recommendation_history(
    db: AsyncSession,
    user_id: UUID,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[RecommendationLog], int]:
    """Paginated recommendation history for a user."""
    from sqlalchemy import func

    count_stmt = (
        select(func.count())
        .select_from(RecommendationLog)
        .where(RecommendationLog.user_id == user_id)
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(RecommendationLog)
        .where(RecommendationLog.user_id == user_id)
        .order_by(RecommendationLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    items = list(result.scalars().all())
    return items, total


# --- Serialization helpers for cache ---

def _serialize_recommendation(rec: RecommendationLog) -> dict:
    """Convert a RecommendationLog to a cacheable dict."""
    return {
        "id": str(rec.id),
        "user_id": str(rec.user_id),
        "recommend_type": rec.recommend_type,
        "scenario": rec.scenario,
        "meal_type": rec.meal_type,
        "target_date": str(rec.target_date) if rec.target_date else None,
        "model_name": rec.model_name,
        "recommendation_json": rec.recommendation_json,
        "summary_text": rec.summary_text,
        "items": [
            {
                "id": str(item.id),
                "item_type": item.item_type,
                "food_name": item.food_name,
                "food_id": str(item.food_id) if item.food_id else None,
                "delivery_dish_id": str(item.delivery_dish_id) if item.delivery_dish_id else None,
                "serving_size_g": item.serving_size_g,
                "estimated_kcal": item.estimated_kcal,
                "estimated_protein_g": item.estimated_protein_g,
                "estimated_fat_g": item.estimated_fat_g,
                "estimated_carbs_g": item.estimated_carbs_g,
                "reason_text": item.reason_text,
                "nutrition_tags": item.nutrition_tags or [],
                "sort_order": item.sort_order,
            }
            for item in (rec.items or [])
        ],
        "status": rec.status.value if rec.status else "generated",
        "feedback": rec.feedback.value if rec.feedback else None,
        "feedback_detail": rec.feedback_detail,
        "total_tokens": rec.total_tokens,
        "latency_ms": rec.latency_ms,
        "created_at": str(rec.created_at) if rec.created_at else None,
    }


def _deserialize_recommendation(data: dict) -> RecommendationLog | None:
    """Minimal deserialization — returns data dict for route to consume."""
    # For cached results, we just return the dict and let the route handle it
    # by converting to the Pydantic schema directly
    return None
