"""
NutriAgent Backend — Nutrition Schemas.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


# ============================================================================
# Dashboard
# ============================================================================


class MacroBreakdown(BaseModel):
    """Macronutrient breakdown for a period."""

    protein_g: float = 0
    fat_g: float = 0
    carbs_g: float = 0
    fiber_g: float = 0
    protein_pct: float = 0
    fat_pct: float = 0
    carbs_pct: float = 0


class MicronutrientStatus(BaseModel):
    """Status of a single micronutrient."""

    name: str
    current: float
    target: float | None = None
    unit: str
    achievement_pct: float | None = None
    status: str = "normal"  # low | normal | high


class DashboardResponse(BaseModel):
    """Nutrition dashboard for a specific day."""

    target_date: date
    total_kcal: float = 0
    kcal_target: int | None = None
    kcal_achievement_pct: float | None = None
    macros: MacroBreakdown = Field(default_factory=MacroBreakdown)
    meal_count: int = 0
    caffeine_mg: float = 0
    caffeine_limit_mg: int = 400
    sodium_mg: float = 0
    fiber_g: float = 0
    nutrition_score: int | None = None
    score_feedback: str | None = None

    # Focus micronutrients for programmers
    lutein_ug: float = 0      # Eye health
    omega3_g: float = 0       # Brain & anti-inflammatory
    vitamin_a_ug: float = 0   # Vision
    vitamin_c_mg: float = 0   # Immunity
    calcium_mg: float = 0     # Bone (sedentary risk)
    magnesium_mg: float = 0   # Sleep & muscle


class WeeklyReportResponse(BaseModel):
    """AI-generated weekly nutrition report."""

    week_start: date
    week_end: date
    avg_daily_kcal: float = 0
    avg_kcal_achievement_pct: float | None = None
    avg_nutrition_score: float | None = None
    total_meals_logged: int = 0
    best_day: date | None = None
    worst_day: date | None = None
    common_deficiencies: list[str] = Field(default_factory=list)
    ai_summary: str = ""
    ai_suggestions: list[str] = Field(default_factory=list)
    macro_trend: dict = Field(default_factory=dict)
