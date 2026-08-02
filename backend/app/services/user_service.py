"""
NutriAgent Backend — User Service.

Handles user profile CRUD, health profile management,
diet types, health goals, allergens, and preferences.
"""

from __future__ import annotations

import json
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.user import (
    User,
    UserAllergen,
    UserDietType,
    UserHealthGoal,
    UserHealthProfile,
    UserPreferences,
)
from app.schemas.user import (
    AllergenItem,
    HealthGoalItem,
    HealthProfileCreate,
    HealthProfileUpdate,
    UserPreferencesUpdate,
    UserProfileUpdate,
)


# ============================================================================
# Profile
# ============================================================================


async def update_user_profile(
    db: AsyncSession,
    user: User,
    data: UserProfileUpdate,
) -> User:
    """Update basic user profile fields."""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    await db.flush()
    await db.refresh(user)
    return user


# ============================================================================
# Health Profile
# ============================================================================


async def get_or_create_health_profile(
    db: AsyncSession,
    user_id: UUID,
) -> UserHealthProfile:
    """Get the user's health profile, creating a default one if absent."""
    result = await db.execute(
        select(UserHealthProfile).where(UserHealthProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        profile = UserHealthProfile(user_id=user_id)
        db.add(profile)
        await db.flush()
        await db.refresh(profile)
    return profile


async def upsert_health_profile(
    db: AsyncSession,
    user_id: UUID,
    data: HealthProfileCreate | HealthProfileUpdate,
) -> UserHealthProfile:
    """Create or update a health profile."""
    profile = await get_or_create_health_profile(db, user_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)
    await db.flush()
    await db.refresh(profile)
    return profile


# ============================================================================
# Health Goals
# ============================================================================


async def set_health_goals(
    db: AsyncSession,
    user_id: UUID,
    goals: list[HealthGoalItem],
) -> list[UserHealthGoal]:
    """Replace all health goals for a user."""
    # Delete existing
    existing = await db.execute(
        select(UserHealthGoal).where(UserHealthGoal.user_id == user_id)
    )
    for goal in existing.scalars().all():
        await db.delete(goal)

    # Insert new
    new_goals = []
    for item in goals:
        goal = UserHealthGoal(
            user_id=user_id,
            goal_type=item.goal_type,
            priority=item.priority,
            is_active=item.is_active,
            target_description=item.target_description,
        )
        db.add(goal)
        new_goals.append(goal)

    await db.flush()
    return new_goals


# ============================================================================
# Diet Types
# ============================================================================


async def set_diet_types(
    db: AsyncSession,
    user_id: UUID,
    diet_types: list[dict],
) -> list[UserDietType]:
    """Replace all diet types for a user."""
    existing = await db.execute(
        select(UserDietType).where(UserDietType.user_id == user_id)
    )
    for dt in existing.scalars().all():
        await db.delete(dt)

    new_types = []
    for item in diet_types:
        dt = UserDietType(
            user_id=user_id,
            diet_type=item["diet_type"],
            is_primary=item.get("is_primary", False),
        )
        db.add(dt)
        new_types.append(dt)

    await db.flush()
    return new_types


# ============================================================================
# Allergens
# ============================================================================


async def set_allergens(
    db: AsyncSession,
    user_id: UUID,
    allergens: list[AllergenItem],
) -> list[UserAllergen]:
    """Replace all allergens for a user."""
    existing = await db.execute(
        select(UserAllergen).where(UserAllergen.user_id == user_id)
    )
    for a in existing.scalars().all():
        await db.delete(a)

    new_allergens = []
    for item in allergens:
        allergen = UserAllergen(
            user_id=user_id,
            allergen=item.allergen,
            severity=item.severity,
            notes=item.notes,
            verified_by_doctor=item.verified_by_doctor,
        )
        db.add(allergen)
        new_allergens.append(allergen)

    await db.flush()
    return new_allergens


# ============================================================================
# Preferences
# ============================================================================


async def get_or_create_preferences(
    db: AsyncSession,
    user_id: UUID,
) -> UserPreferences:
    """Get user preferences, creating defaults if absent."""
    result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == user_id)
    )
    prefs = result.scalar_one_or_none()
    if not prefs:
        prefs = UserPreferences(user_id=user_id)
        db.add(prefs)
        await db.flush()
        await db.refresh(prefs)
    return prefs


async def update_preferences(
    db: AsyncSession,
    user_id: UUID,
    data: UserPreferencesUpdate,
) -> UserPreferences:
    """Update user preferences (partial update)."""
    prefs = await get_or_create_preferences(db, user_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(prefs, key, value)
    await db.flush()
    await db.refresh(prefs)
    return prefs


# ============================================================================
# Full Profile Query
# ============================================================================


async def get_full_user_profile(db: AsyncSession, user: User) -> dict:
    """
    Assemble the complete user profile including health, goals, allergens,
    diet types, and preferences. Returns a dict ready for UserProfileRead.
    """
    # Eager-load relationships
    health_profile = await get_or_create_health_profile(db, user.id)
    preferences = await get_or_create_preferences(db, user.id)

    # Build response dict
    return {
        "id": user.id,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "gender": user.gender.value if user.gender else None,
        "email": user.email,
        "phone": user.phone,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "health_profile": health_profile,
        "diet_types": user.diet_types,
        "health_goals": user.health_goals,
        "allergens": user.allergens,
        "preferences": preferences,
    }
