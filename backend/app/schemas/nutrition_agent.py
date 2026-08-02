"""
NutriAgent Backend — Nutrition Agent Schemas.

FoodRecord (input) and NutritionAnalysis (output) for the
diet analysis agent powered by LangGraph.
"""

from __future__ import annotations

from datetime import date, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Input: FoodRecord
# ============================================================================


class FoodItemRecord(BaseModel):
    """A single food item within a meal."""

    food_name: str = Field(..., min_length=1, max_length=256, description="食物名称")
    food_id: UUID | None = Field(None, description="关联标准食物库ID")
    serving_size_g: float = Field(..., gt=0, description="食用份量（克）")
    energy_kcal: float = Field(..., ge=0, description="热量 (kcal)")
    protein_g: float = Field(0, ge=0, description="蛋白质 (g)")
    fat_g: float = Field(0, ge=0, description="脂肪 (g)")
    carbs_g: float = Field(0, ge=0, description="碳水化合物 (g)")
    fiber_g: float = Field(0, ge=0, description="膳食纤维 (g)")
    sodium_mg: float = Field(0, ge=0, description="钠 (mg)")
    sugar_g: float = Field(0, ge=0, description="糖 (g)")
    caffeine_mg: float = Field(0, ge=0, description="咖啡因 (mg)")
    is_processed: bool = Field(False, description="是否加工食品")


class MealRecord(BaseModel):
    """A single meal containing one or more food items."""

    meal_type: Literal["breakfast", "lunch", "dinner", "snack", "late_night"] = Field(
        ..., description="餐次类型"
    )
    meal_time: time | None = Field(None, description="用餐时间")
    location: Literal["home", "office", "restaurant", "delivery", "convenience_store", "other"] = Field(
        "other", description="用餐地点"
    )
    satiety_level: int | None = Field(None, ge=1, le=5, description="饱腹感 1-5")
    mood_before: int | None = Field(None, ge=1, le=5, description="餐前心情 1-5")
    mood_after: int | None = Field(None, ge=1, le=5, description="餐后心情 1-5")
    items: list[FoodItemRecord] = Field(..., min_length=1, max_length=30, description="食物列表")


class UserProfileSnapshot(BaseModel):
    """Snapshot of relevant user profile data for nutrition analysis."""

    age: int | None = Field(None, ge=0, le=150)
    gender: Literal["male", "female", "other"] | None = None
    height_cm: float | None = Field(None, ge=50, le=300)
    weight_kg: float | None = Field(None, ge=20, le=500)
    bmi: float | None = None
    bmr_kcal: float | None = None
    activity_level: Literal["sedentary", "light", "moderate", "active", "very_active"] = "sedentary"
    daily_kcal_target: int = Field(2000, ge=800, le=6000)
    target_protein_pct: float = Field(20, ge=5, le=60)
    target_fat_pct: float = Field(30, ge=5, le=70)
    target_carbs_pct: float = Field(50, ge=5, le=80)
    diet_types: list[str] = Field(default_factory=list)
    health_goals: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)
    food_blacklist: list[str] = Field(default_factory=list)
    spice_level: int | None = Field(None, ge=0, le=5)
    oil_level: int | None = Field(None, ge=0, le=5)


class FoodRecord(BaseModel):
    """Complete food record for a day — input to the Nutrition Agent."""

    user_id: UUID | None = Field(None, description="用户ID（可选，用于关联用户数据）")
    target_date: date = Field(..., description="分析的目标日期")
    meals: list[MealRecord] = Field(..., min_length=1, max_length=8, description="当日所有餐次")
    user_profile: UserProfileSnapshot | None = Field(None, description="用户画像快照")
    notes: str | None = Field(None, max_length=500, description="额外备注")
    extra: dict = Field(default_factory=dict, description="扩展字段")


# ============================================================================
# Output: NutritionAnalysis
# ============================================================================


class DimensionScore(BaseModel):
    """Score for a single nutrition dimension (0-100)."""

    dimension: str = Field(..., description="维度名称")
    score: float = Field(..., ge=0, le=100, description="得分 0-100")
    weight: float = Field(..., ge=0, le=1, description="权重")
    weighted_score: float = Field(..., ge=0, le=100, description="加权得分")
    grade: Literal["A", "B", "C", "D", "F"] = Field(..., description="等级")
    details: list[str] = Field(default_factory=list, description="评分详情")
    suggestions: list[str] = Field(default_factory=list, description="改进建议")


class MacroBalance(BaseModel):
    """Macronutrient balance analysis."""

    protein_g: float = 0
    fat_g: float = 0
    carbs_g: float = 0
    fiber_g: float = 0
    protein_pct: float = 0
    fat_pct: float = 0
    carbs_pct: float = 0
    protein_target_g: float | None = None
    fat_target_g: float | None = None
    carbs_target_g: float | None = None
    fiber_target_g: float = 25
    protein_status: Literal["low", "normal", "high"] = "normal"
    fat_status: Literal["low", "normal", "high"] = "normal"
    carbs_status: Literal["low", "normal", "high"] = "normal"
    fiber_status: Literal["low", "normal", "high"] = "normal"


class MealTimingAnalysis(BaseModel):
    """Meal timing and distribution analysis."""

    meal_count: int = 0
    breakfast_kcal_pct: float = 0
    lunch_kcal_pct: float = 0
    dinner_kcal_pct: float = 0
    snack_kcal_pct: float = 0
    late_night_kcal: float = 0
    has_breakfast: bool = False
    has_late_night: bool = False
    meal_gap_hours: float | None = None
    timing_score: float = Field(0, ge=0, le=100)
    timing_notes: list[str] = Field(default_factory=list)


class MicronutrientGap(BaseModel):
    """A single micronutrient deficiency or excess."""

    nutrient: str
    current_value: float
    target_value: float | None = None
    unit: str
    gap_pct: float | None = None
    severity: Literal["critical", "moderate", "mild", "optimal"] = "optimal"
    food_sources: list[str] = Field(default_factory=list)


class NutritionAnalysis(BaseModel):
    """Complete AI-powered nutrition analysis result — output of Nutrition Agent."""

    # Identity
    target_date: date
    user_id: UUID | None = None

    # Overall health score
    health_score: float = Field(..., ge=0, le=100, description="综合健康评分 0-100")
    health_grade: Literal["A", "B", "C", "D", "F"] = Field(..., description="综合等级")
    score_summary: str = Field("", description="评分概述")

    # Dimension scores
    dimensions: list[DimensionScore] = Field(default_factory=list)

    # Detailed analysis
    total_kcal: float = 0
    kcal_target: int = 2000
    kcal_achievement_pct: float = 0
    macro_balance: MacroBalance = Field(default_factory=MacroBalance)
    meal_timing: MealTimingAnalysis = Field(default_factory=MealTimingAnalysis)
    food_variety_count: int = Field(0, description="食物种类数")
    processed_food_pct: float = Field(0, description="加工食品占比")

    # Micronutrient gaps
    micronutrient_gaps: list[MicronutrientGap] = Field(default_factory=list)

    # AI-generated insights
    ai_summary: str = Field("", description="AI 综合分析摘要")
    ai_strengths: list[str] = Field(default_factory=list, description="饮食优点")
    ai_weaknesses: list[str] = Field(default_factory=list, description="饮食问题")
    ai_suggestions: list[str] = Field(default_factory=list, description="AI 改进建议")
    ai_meal_ideas: list[str] = Field(default_factory=list, description="明日饮食建议")

    # Metadata
    model_name: str = ""
    analysis_latency_ms: int | None = None
    warnings: list[str] = Field(default_factory=list)
