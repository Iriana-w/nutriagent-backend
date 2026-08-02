"""
NutriAgent Backend — User Routes.

GET    /api/v1/users/me
PATCH  /api/v1/users/me
GET    /api/v1/users/me/profile          # Full profile with health data
PATCH  /api/v1/users/me/health-profile
PUT    /api/v1/users/me/health-goals
PUT    /api/v1/users/me/diet-types
PUT    /api/v1/users/me/allergens
GET    /api/v1/users/me/preferences
PATCH  /api/v1/users/me/preferences
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUserId, DBSession
from app.schemas.user import (
    AllergenItem,
    DietTypeItem,
    HealthGoalItem,
    HealthProfileCreate,
    HealthProfileRead,
    HealthProfileUpdate,
    UserPreferencesRead,
    UserPreferencesUpdate,
    UserProfileRead,
    UserProfileUpdate,
    UserRead,
)
from app.services.auth_service import get_user_by_id
from app.services.user_service import (
    get_full_user_profile,
    set_allergens,
    set_diet_types,
    set_health_goals,
    update_preferences,
    update_user_profile,
    upsert_health_profile,
)

router = APIRouter(prefix="/users", tags=["Users"])


# --- Basic Profile ---


@router.get("/me", response_model=UserRead)
async def get_me(db: DBSession, user_id: CurrentUserId) -> UserRead:
    """Get the current user's basic profile."""
    user = await get_user_by_id(db, user_id)
    return UserRead.model_validate(user)


@router.patch("/me", response_model=UserRead)
async def update_me(
    db: DBSession,
    user_id: CurrentUserId,
    data: UserProfileUpdate,
) -> UserRead:
    """Update the current user's basic profile fields."""
    user = await get_user_by_id(db, user_id)
    user = await update_user_profile(db, user, data)
    return UserRead.model_validate(user)


# --- Full Profile ---


@router.get("/me/profile", response_model=UserProfileRead)
async def get_full_profile(db: DBSession, user_id: CurrentUserId) -> UserProfileRead:
    """Get the current user's complete profile including health data."""
    import traceback
    user = await get_user_by_id(db, user_id)
    try:
        profile_data = await get_full_user_profile(db, user)
        return UserProfileRead(**profile_data)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc(),
            },
        )


# --- Health Profile ---


@router.patch("/me/health-profile", response_model=HealthProfileRead)
async def update_health_profile(
    db: DBSession,
    user_id: CurrentUserId,
    data: HealthProfileUpdate,
) -> HealthProfileRead:
    """Update the user's health profile (partial update)."""
    profile = await upsert_health_profile(db, UUID(user_id), data)
    return HealthProfileRead.model_validate(profile)


# --- Health Goals ---


@router.put("/me/health-goals", response_model=list[HealthGoalItem])
async def put_health_goals(
    db: DBSession,
    user_id: CurrentUserId,
    data: list[HealthGoalItem],
) -> list[HealthGoalItem]:
    """Replace all health goals for the current user."""
    goals = await set_health_goals(db, UUID(user_id), data)
    return [HealthGoalItem.model_validate(g) for g in goals]


# --- Diet Types ---


@router.put("/me/diet-types", response_model=list[DietTypeItem])
async def put_diet_types(
    db: DBSession,
    user_id: CurrentUserId,
    data: list[DietTypeItem],
) -> list[DietTypeItem]:
    """Replace all diet types for the current user."""
    raw = [{"diet_type": d.diet_type, "is_primary": d.is_primary} for d in data]
    types = await set_diet_types(db, UUID(user_id), raw)
    return [DietTypeItem.model_validate(t) for t in types]


# --- Allergens ---


@router.put("/me/allergens", response_model=list[AllergenItem])
async def put_allergens(
    db: DBSession,
    user_id: CurrentUserId,
    data: list[AllergenItem],
) -> list[AllergenItem]:
    """Replace all allergens for the current user."""
    allergens = await set_allergens(db, UUID(user_id), data)
    return [AllergenItem.model_validate(a) for a in allergens]


# --- Preferences ---


@router.get("/me/preferences", response_model=UserPreferencesRead)
async def get_preferences(
    db: DBSession,
    user_id: CurrentUserId,
) -> UserPreferencesRead:
    """Get the current user's food preferences."""
    from app.services.user_service import get_or_create_preferences

    prefs = await get_or_create_preferences(db, UUID(user_id))
    return UserPreferencesRead.model_validate(prefs)


@router.patch("/me/preferences", response_model=UserPreferencesRead)
async def patch_preferences(
    db: DBSession,
    user_id: CurrentUserId,
    data: UserPreferencesUpdate,
) -> UserPreferencesRead:
    """Update the current user's food preferences (partial update)."""
    prefs = await update_preferences(db, UUID(user_id), data)
    return UserPreferencesRead.model_validate(prefs)
