"""
NutriAgent Backend — Recommendation Schemas.

Request & response models for the AI recommendation engine.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Request Schemas
# ============================================================================


class MealRecommendRequest(BaseModel):
    """Request a single meal recommendation."""

    meal_type: str = Field(
        ..., description="breakfast | lunch | dinner | snack | late_night"
    )
    scenario: str | None = Field(
        None,
        description="overtime | eye_care | hair_care | caffeine_cut | energy_boost | party_survival | travel",
    )
    budget_cent: int | None = Field(None, description="Max budget in cents")
    delivery_only: bool = Field(False, description="Only recommend delivery dishes")
    lat: float | None = Field(None, ge=-90, le=90, description="Latitude for delivery search")
    lng: float | None = Field(None, ge=-180, le=180, description="Longitude for delivery search")
    exclude_foods: list[str] = Field(default_factory=list, description="Foods to exclude")


class DailyRecommendRequest(BaseModel):
    """Request a full day meal plan."""

    target_date: date | None = Field(None, description="Date to plan for (default: today)")
    scenario: str | None = None
    budget_cent: int | None = None
    delivery_only: bool = False
    lat: float | None = None
    lng: float | None = None
    exclude_foods: list[str] = Field(default_factory=list)


class WeeklyPlanRequest(BaseModel):
    """Request a weekly meal plan."""

    week_start: date = Field(..., description="Monday of the target week")
    scenario: str | None = None
    budget_cent: int | None = None


class ScenarioRequest(BaseModel):
    """Request a scenario-based recommendation."""

    scenario: str = Field(
        ...,
        description="overtime | eye_care | hair_care | caffeine_cut | energy_boost | party_survival | travel",
    )
    meal_type: str | None = None


class FeedbackRequest(BaseModel):
    """Submit feedback on a recommendation."""

    feedback: str = Field(..., description="positive | negative | neutral | skip")
    detail: str | None = Field(None, description="Optional text feedback")
    item_feedbacks: dict[str, str] | None = Field(
        None, description="Map of item_id -> feedback for per-item feedback"
    )


# ============================================================================
# Response Schemas
# ============================================================================


class RecommendationItemRead(BaseModel):
    """A single food/dish recommendation item."""

    id: UUID
    item_type: str = "food"
    food_name: str
    food_id: UUID | None = None
    delivery_dish_id: UUID | None = None
    serving_size_g: float | None = None
    estimated_kcal: float | None = None
    estimated_protein_g: float | None = None
    estimated_fat_g: float | None = None
    estimated_carbs_g: float | None = None
    reason_text: str | None = None
    nutrition_tags: list[str] = Field(default_factory=list)
    sort_order: int = 0

    model_config = {"from_attributes": True}


class RecommendationRead(BaseModel):
    """Full recommendation result."""

    id: UUID
    user_id: UUID
    recommend_type: str
    scenario: str | None = None
    meal_type: str | None = None
    target_date: date | None = None
    model_name: str
    summary_text: str
    recommendation_json: dict = Field(default_factory=dict)
    items: list[RecommendationItemRead] = Field(default_factory=list)
    status: str = "generated"
    feedback: str | None = None
    feedback_detail: str | None = None
    total_tokens: int | None = None
    latency_ms: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# Meal Plan
# ============================================================================


class MealPlanItemRead(BaseModel):
    id: UUID
    plan_date: date
    meal_type: str
    food_name: str
    food_id: UUID | None = None
    serving_size_g: float | None = None
    estimated_kcal: float | None = None
    is_completed: bool = False
    sort_order: int = 0

    model_config = {"from_attributes": True}


class MealPlanRead(BaseModel):
    id: UUID
    user_id: UUID
    plan_week_start: date
    plan_name: str | None = None
    status: str = "active"
    daily_kcal_target: int | None = None
    daily_protein_g: float | None = None
    daily_fat_g: float | None = None
    daily_carbs_g: float | None = None
    notes: str | None = None
    items: list[MealPlanItemRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
