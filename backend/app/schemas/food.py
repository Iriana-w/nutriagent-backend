"""
NutriAgent Backend — Food & Delivery Schemas.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Food
# ============================================================================


class FoodCategoryRead(BaseModel):
    id: int
    category: str
    parent_id: int | None = None
    name_zh: str
    icon_emoji: str | None = None
    sort_order: int = 0

    model_config = {"from_attributes": True}


class FoodBrief(BaseModel):
    """Brief food info for list displays."""

    id: UUID
    name_zh: str
    name_en: str | None = None
    category_id: int
    energy_kcal: float
    protein_g: float = 0
    fat_g: float = 0
    carbs_g: float = 0
    thumb_url: str | None = None
    is_common: bool = False
    category_name: str | None = None

    model_config = {"from_attributes": True}


class FoodRead(FoodBrief):
    """Full food nutrition data."""

    alias: list[str] = Field(default_factory=list)
    energy_kj: float | None = None
    fiber_g: float = 0
    sugar_g: float = 0
    sodium_mg: float = 0
    cholesterol_mg: float = 0
    vitamin_a_ug: float | None = None
    vitamin_c_mg: float | None = None
    vitamin_e_mg: float | None = None
    lutein_ug: float | None = None
    omega3_g: float | None = None
    caffeine_mg: float | None = None
    calcium_mg: float | None = None
    iron_mg: float | None = None
    zinc_mg: float | None = None
    magnesium_mg: float | None = None
    glycemic_index: int | None = None
    edible_portion_pct: float = 100
    is_processed: bool = False
    data_source: str = "中国食物成分表"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class FoodSearchRequest(BaseModel):
    """Semantic or keyword food search."""

    query: str = Field(..., min_length=1, max_length=256, description="Search query")
    category: str | None = Field(None, description="Filter by category")
    min_protein: float | None = Field(None, ge=0)
    max_kcal: float | None = Field(None, ge=0)
    limit: int = Field(20, ge=1, le=100)


# ============================================================================
# Delivery
# ============================================================================


class DeliveryDishRead(BaseModel):
    id: UUID
    platform: str
    dish_name: str
    merchant_name: str
    price_cent: int
    image_url: str | None = None
    estimated_kcal: int | None = None
    estimated_protein_g: float | None = None
    estimated_fat_g: float | None = None
    estimated_carbs_g: float | None = None
    health_score: int | None = None
    merchant_lat: float | None = None
    merchant_lng: float | None = None
    merchant_address: str | None = None

    model_config = {"from_attributes": True}


class DeliverySearchRequest(BaseModel):
    """Search nearby healthy delivery options."""

    query: str = Field("", description="Search keyword")
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(3.0, ge=0.1, le=20)
    budget_cent: int | None = Field(None, description="Max price in cents")
    min_health_score: int = Field(50, ge=0, le=100)
    limit: int = Field(20, ge=1, le=50)
