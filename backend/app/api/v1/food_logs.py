"""
NutriAgent Backend — Food Log Routes.

POST   /api/v1/food-logs
GET    /api/v1/food-logs
GET    /api/v1/food-logs/{id}
POST   /api/v1/food-logs/{id}/items
DELETE /api/v1/food-logs/{id}
POST   /api/v1/food-logs/photo         # Photo food recognition
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Path

from app.api.deps import CurrentUserId, DBSession, Pagination
from app.schemas.common import PaginatedResponse
from app.schemas.food_log import (
    FoodLogCreate,
    FoodLogItemCreate,
    FoodLogItemRead,
    FoodLogQueryParams,
    FoodLogRead,
)
from app.services.food_log_service import (
    add_item_to_log,
    create_food_log,
    delete_food_log,
    get_food_log,
    list_food_logs,
)

router = APIRouter(prefix="/food-logs", tags=["Food Logs"])


@router.post("", response_model=FoodLogRead, status_code=201)
async def create_log(
    db: DBSession,
    user_id: CurrentUserId,
    data: FoodLogCreate,
) -> FoodLogRead:
    """Record a meal. Includes one or more food items with nutrition data."""
    food_log = await create_food_log(db, UUID(user_id), data)
    return FoodLogRead.model_validate(food_log)


@router.get("", response_model=PaginatedResponse[FoodLogRead])
async def list_logs(
    db: DBSession,
    user_id: CurrentUserId,
    pagination: Pagination,
    start_date: str | None = None,
    end_date: str | None = None,
    meal_type: str | None = None,
) -> PaginatedResponse[FoodLogRead]:
    """Get paginated food logs for the current user with optional filters."""
    from datetime import date as date_type

    items, total = await list_food_logs(
        db,
        UUID(user_id),
        start_date=date_type.fromisoformat(start_date) if start_date else None,
        end_date=date_type.fromisoformat(end_date) if end_date else None,
        meal_type=meal_type,
        page=pagination["page"],
        page_size=pagination["page_size"],
    )
    return PaginatedResponse.from_items(
        items=[FoodLogRead.model_validate(r) for r in items],
        total=total,
        page=pagination["page"],
        page_size=pagination["page_size"],
    )


@router.get("/{log_id}", response_model=FoodLogRead)
async def get_log(
    db: DBSession,
    user_id: CurrentUserId,
    log_id: UUID = Path(...),
) -> FoodLogRead:
    """Get a single food log by ID."""
    food_log = await get_food_log(db, log_id, UUID(user_id))
    return FoodLogRead.model_validate(food_log)


@router.post("/{log_id}/items", response_model=FoodLogItemRead, status_code=201)
async def add_item(
    db: DBSession,
    user_id: CurrentUserId,
    log_id: UUID = Path(...),
    data: FoodLogItemCreate = ...,
) -> FoodLogItemRead:
    """Add a single food item to an existing food log."""
    item = await add_item_to_log(db, log_id, UUID(user_id), data)
    return FoodLogItemRead.model_validate(item)


@router.delete("/{log_id}", status_code=204)
async def delete_log(
    db: DBSession,
    user_id: CurrentUserId,
    log_id: UUID = Path(...),
) -> None:
    """Delete a food log and all its items."""
    await delete_food_log(db, log_id, UUID(user_id))


@router.post("/photo", status_code=202)
async def recognize_food_from_photo(
    user_id: CurrentUserId,
) -> dict:
    """
    Upload a food photo for AI recognition.
    Returns recognized food items with estimated nutrition.
    (Placeholder — requires image upload handling and vision model)
    """
    return {
        "status": "pending",
        "message": "Food photo recognition will be processed asynchronously. "
                   "Please check back for results.",
    }
