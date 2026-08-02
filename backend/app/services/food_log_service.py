"""
NutriAgent Backend — Food Log Service.

Handles creating, reading, and querying food logs and items.
"""

from __future__ import annotations

import time as time_module
from datetime import date, datetime, time
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.food_log import (
    DailyNutritionSummary,
    FoodLog,
    FoodLogItem,
    MealTypeEnum,
)
from app.schemas.food_log import FoodLogCreate, FoodLogItemCreate


async def create_food_log(
    db: AsyncSession,
    user_id: UUID,
    data: FoodLogCreate,
) -> FoodLog:
    """Create a food log with items. Totals are auto-calculated by DB trigger."""
    now = datetime.utcnow()
    food_log = FoodLog(
        user_id=user_id,
        meal_type=MealTypeEnum(data.meal_type),
        meal_date=data.meal_date,
        meal_time=data.meal_time or time(now.hour, now.minute, now.second),
        source=data.source,
        mood_before=data.mood_before,
        mood_after=data.mood_after,
        satiety_level=data.satiety_level,
        notes=data.notes,
        photo_url=data.photo_url,
        location=data.location,
        cost_cent=data.cost_cent,
    )
    db.add(food_log)
    await db.flush()

    # Create items (values are absolute, not per-100g)
    for i, item_data in enumerate(data.items):
        item = FoodLogItem(
            food_log_id=food_log.id,
            food_id=item_data.food_id,
            food_name=item_data.food_name,
            serving_size_g=item_data.serving_size_g,
            serving_unit=item_data.serving_unit,
            energy_kcal=item_data.energy_kcal,
            protein_g=item_data.protein_g,
            fat_g=item_data.fat_g,
            carbs_g=item_data.carbs_g,
            fiber_g=item_data.fiber_g,
            sodium_mg=item_data.sodium_mg,
            caffeine_mg=item_data.caffeine_mg,
            sort_order=item_data.sort_order or i,
        )
        db.add(item)

    await db.flush()
    await db.refresh(food_log)
    return food_log


def _calc_per_serving(value_per_100g: float, serving_g: float) -> float:
    """Convert per-100g nutrition values to actual serving size."""
    return round(value_per_100g * serving_g / 100.0, 2)


async def get_food_log(db: AsyncSession, log_id: UUID, user_id: UUID) -> FoodLog:
    """Get a single food log by ID, verified to belong to the user."""
    result = await db.execute(
        select(FoodLog).where(
            and_(FoodLog.id == log_id, FoodLog.user_id == user_id)
        )
    )
    food_log = result.scalar_one_or_none()
    if not food_log:
        raise NotFoundError("FoodLog", str(log_id))
    return food_log


async def list_food_logs(
    db: AsyncSession,
    user_id: UUID,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    meal_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[FoodLog], int]:
    """Paginated food log listing with optional date/meal filters."""
    conditions = [FoodLog.user_id == user_id]
    if start_date:
        conditions.append(FoodLog.meal_date >= start_date)
    if end_date:
        conditions.append(FoodLog.meal_date <= end_date)
    if meal_type:
        conditions.append(FoodLog.meal_type == MealTypeEnum(meal_type))

    # Count
    count_stmt = select(func.count()).select_from(FoodLog).where(and_(*conditions))
    total = (await db.execute(count_stmt)).scalar() or 0

    # Fetch
    stmt = (
        select(FoodLog)
        .where(and_(*conditions))
        .order_by(FoodLog.meal_date.desc(), FoodLog.meal_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    return items, total


async def delete_food_log(db: AsyncSession, log_id: UUID, user_id: UUID) -> bool:
    """Delete a food log. Returns True if deleted, False if not found."""
    food_log = await get_food_log(db, log_id, user_id)
    await db.delete(food_log)
    await db.flush()
    return True


async def add_item_to_log(
    db: AsyncSession,
    log_id: UUID,
    user_id: UUID,
    item_data: FoodLogItemCreate,
) -> FoodLogItem:
    """Add a single food item to an existing log."""
    food_log = await get_food_log(db, log_id, user_id)
    item = FoodLogItem(
        food_log_id=food_log.id,
        food_id=item_data.food_id,
        food_name=item_data.food_name,
        serving_size_g=item_data.serving_size_g,
        serving_unit=item_data.serving_unit,
        energy_kcal=_calc_per_serving(item_data.energy_kcal, item_data.serving_size_g),
        protein_g=_calc_per_serving(item_data.protein_g, item_data.serving_size_g),
        fat_g=_calc_per_serving(item_data.fat_g, item_data.serving_size_g),
        carbs_g=_calc_per_serving(item_data.carbs_g, item_data.serving_size_g),
        fiber_g=_calc_per_serving(item_data.fiber_g, item_data.serving_size_g),
        sodium_mg=_calc_per_serving(item_data.sodium_mg, item_data.serving_size_g),
        caffeine_mg=_calc_per_serving(item_data.caffeine_mg, item_data.serving_size_g),
        sort_order=item_data.sort_order,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item
