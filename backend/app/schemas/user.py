"""
NutriAgent Backend — User & Health Profile Schemas.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Health Profile
# ============================================================================


class HealthProfileBase(BaseModel):
    gender: str | None = Field(None, description="male | female | other | prefer_not_to_say")
    birth_date: date | None = None
    height_cm: float | None = Field(None, ge=50, le=300)
    weight_kg: float | None = Field(None, ge=20, le=500)
    body_fat_pct: float | None = Field(None, ge=1, le=70)
    muscle_mass_kg: float | None = None
    waist_cm: float | None = None
    daily_kcal_target: int | None = Field(None, ge=800, le=6000)
    target_protein_pct: float = Field(20, ge=5, le=60)
    target_fat_pct: float = Field(30, ge=5, le=70)
    target_carbs_pct: float = Field(50, ge=5, le=80)
    activity_level: str = Field("sedentary", description="sedentary | light | moderate | active | very_active")


class HealthProfileCreate(HealthProfileBase):
    """Create a health profile for the current user."""
    pass


class HealthProfileUpdate(HealthProfileBase):
    """Update health profile fields. Only provided fields are updated."""
    pass


class HealthProfileRead(HealthProfileBase):
    """Health profile as returned by the API."""

    id: UUID
    user_id: UUID
    bmi: float | None = None
    bmr_kcal: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# Diet Types, Goals, Allergens, Preferences
# ============================================================================


class DietTypeItem(BaseModel):
    diet_type: str
    is_primary: bool = False

    model_config = {"from_attributes": True}


class HealthGoalItem(BaseModel):
    id: UUID | None = None
    goal_type: str
    priority: int = Field(0, ge=0, le=10)
    is_active: bool = True
    target_description: str | None = None

    model_config = {"from_attributes": True}


class AllergenItem(BaseModel):
    id: UUID | None = None
    allergen: str = Field(..., max_length=100)
    severity: str = "moderate"  # mild | moderate | severe
    notes: str | None = None
    verified_by_doctor: bool = False

    model_config = {"from_attributes": True}


class UserPreferencesRead(BaseModel):
    spice_level: int | None = None
    sweet_level: int | None = None
    oil_level: int | None = None
    budget_per_meal: int | None = None
    cuisine_prefs: dict = Field(default_factory=dict)
    food_blacklist: list = Field(default_factory=list)
    food_whitelist: list = Field(default_factory=list)
    cooking_prefs: dict = Field(default_factory=dict)
    meal_schedule: dict = Field(default_factory=dict)
    extra: dict = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class UserPreferencesUpdate(BaseModel):
    spice_level: int | None = Field(None, ge=0, le=5)
    sweet_level: int | None = Field(None, ge=0, le=5)
    oil_level: int | None = Field(None, ge=0, le=5)
    budget_per_meal: int | None = Field(None, gt=0)
    cuisine_prefs: dict | None = None
    food_blacklist: list | None = None
    food_whitelist: list | None = None
    cooking_prefs: dict | None = None
    meal_schedule: dict | None = None
    extra: dict | None = None


# ============================================================================
# Full User Profile (composite)
# ============================================================================


class UserRead(BaseModel):
    """Publicly visible user info."""

    id: UUID
    nickname: str
    avatar_url: str | None = None
    gender: str | None = None
    email: str | None = None
    phone: str | None = None
    is_active: bool = True
    created_at: datetime

    model_config = {"from_attributes": True}


class UserProfileRead(UserRead):
    """Full user profile including health & preferences."""

    health_profile: HealthProfileRead | None = None
    diet_types: list[DietTypeItem] = Field(default_factory=list)
    health_goals: list[HealthGoalItem] = Field(default_factory=list)
    allergens: list[AllergenItem] = Field(default_factory=list)
    preferences: UserPreferencesRead | None = None


class UserProfileUpdate(BaseModel):
    """Fields the user can update on their own profile."""

    nickname: str | None = Field(None, min_length=1, max_length=64)
    avatar_url: str | None = None
    gender: str | None = None


# ============================================================================
# Caffeine Log
# ============================================================================


class CaffeineLogRead(BaseModel):
    id: UUID
    log_date: date
    total_mg: int
    drink_count: int
    target_limit_mg: int
    over_limit: bool | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
