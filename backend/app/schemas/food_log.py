"""
NutriAgent Backend — Food Log Schemas.
"""

from __future__ import annotations

from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Food Log Item
# ============================================================================


class FoodLogItemCreate(BaseModel):
    """Create a single food item within a meal log."""

    food_id: UUID | None = Field(None, description="Standard food DB ID (optional)")
    food_name: str = Field(..., min_length=1, max_length=256)
    serving_size_g: float = Field(..., gt=0, description="Serving size in grams")
    serving_unit: str = Field("g")
    energy_kcal: float = Field(..., ge=0)
    protein_g: float = Field(0, ge=0)
    fat_g: float = Field(0, ge=0)
    carbs_g: float = Field(0, ge=0)
    fiber_g: float = Field(0, ge=0)
    sodium_mg: float = Field(0, ge=0)
    caffeine_mg: float = Field(0, ge=0)
    sort_order: int = 0


class FoodLogItemRead(BaseModel):
    id: UUID
    food_id: UUID | None = None
    food_name: str
    serving_size_g: float
    serving_unit: str
    energy_kcal: float
    protein_g: float = 0
    fat_g: float = 0
    carbs_g: float = 0
    fiber_g: float = 0
    sodium_mg: float = 0
    caffeine_mg: float = 0
    sort_order: int = 0

    model_config = {"from_attributes": True}


# ============================================================================
# Food Log
# ============================================================================


class FoodLogCreate(BaseModel):
    """Create a meal record."""

    meal_type: str = Field(..., description="breakfast | lunch | dinner | snack | late_night")
    meal_date: date = Field(default_factory=date.today)
    meal_time: time | None = None
    source: str = Field("manual", description="manual | photo | voice | delivery_order | ai_estimate")
    items: list[FoodLogItemCreate] = Field(..., min_length=1, max_length=50)
    mood_before: int | None = Field(None, ge=1, le=5)
    mood_after: int | None = Field(None, ge=1, le=5)
    satiety_level: int | None = Field(None, ge=1, le=5)
    notes: str | None = None
    photo_url: str | None = None
    location: str | None = None
    cost_cent: int | None = None


class FoodLogRead(BaseModel):
    id: UUID
    user_id: UUID
    meal_type: str
    meal_date: date
    meal_time: time | None = None
    source: str
    total_kcal: float = 0
    total_protein_g: float = 0
    total_fat_g: float = 0
    total_carbs_g: float = 0
    total_fiber_g: float = 0
    total_sodium_mg: float = 0
    total_caffeine_mg: float = 0
    items: list[FoodLogItemRead] = Field(default_factory=list)
    mood_before: int | None = None
    mood_after: int | None = None
    satiety_level: int | None = None
    notes: str | None = None
    photo_url: str | None = None
    location: str | None = None
    cost_cent: int | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# ============================================================================
# Nutrition Summary
# ============================================================================


class NutritionSummaryRead(BaseModel):
    id: UUID
    user_id: UUID
    summary_date: date
    total_kcal: float = 0
    total_protein_g: float = 0
    total_fat_g: float = 0
    total_carbs_g: float = 0
    total_fiber_g: float = 0
    total_sodium_mg: float = 0
    total_caffeine_mg: float = 0
    kcal_target: int | None = None
    kcal_achievement_pct: float | None = None
    meal_count: int = 0
    nutrition_score: int | None = None
    score_feedback: str | None = None
    generated_at: datetime

    model_config = {"from_attributes": True}


class FoodLogQueryParams(BaseModel):
    """Query parameters for food log listing."""

    start_date: date | None = None
    end_date: date | None = None
    meal_type: str | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
