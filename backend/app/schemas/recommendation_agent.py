"""
NutriAgent Backend — Recommendation Agent Schemas.

Input (RecommendationRequest) and Output (MealRecommendation) for the
next-meal recommendation agent powered by LangGraph.

Key inputs the agent considers:
- user_history: recent meals, feedback patterns, preference signals
- health_goals: active goals with priorities
- budget: per-meal budget constraint
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Input: User History
# ============================================================================


class RecentMealItem(BaseModel):
    """A single food item from recent history."""

    food_name: str
    meal_type: str
    meal_date: date
    energy_kcal: float = 0
    was_liked: bool | None = None  # from feedback


class HistorySummary(BaseModel):
    """Summarized user diet history for the agent."""

    recent_meals: list[RecentMealItem] = Field(default_factory=list, description="最近3-7天的饮食记录")
    recent_food_names: list[str] = Field(default_factory=list, description="最近吃过的食物名称（去重）")
    avg_daily_kcal: float | None = Field(None, description="近期日均热量摄入")
    avg_protein_g: float | None = Field(None, description="近期日均蛋白质摄入")
    common_meal_types: list[str] = Field(default_factory=list, description="常吃的餐次类型")
    skipped_meals: list[str] = Field(default_factory=list, description="常跳过的餐次")
    liked_foods: list[str] = Field(default_factory=list, description="用户点赞过的食物")
    disliked_foods: list[str] = Field(default_factory=list, description="用户踩过的食物")
    nutrition_gaps: list[str] = Field(default_factory=list, description="AI识别的营养缺口")


# ============================================================================
# Input: Health Goals
# ============================================================================


class HealthGoalInput(BaseModel):
    """A single health goal for the agent to consider."""

    goal_type: str = Field(..., description="lose_weight | gain_muscle | eye_health | ...")
    priority: int = Field(0, ge=0, le=10)
    description: str | None = None


# ============================================================================
# Input: RecommendationRequest
# ============================================================================


class RecommendationRequest(BaseModel):
    """
    Request for a personalized next-meal recommendation.

    The agent uses three primary signals:
    1. user_history — what you've been eating, likes/dislikes, nutrition gaps
    2. health_goals — your active health objectives with priorities
    3. budget — how much you want to spend on this meal
    """

    user_id: UUID | None = Field(None, description="用户ID")

    # --- Core Inputs ---
    user_history: HistorySummary | None = Field(None, description="用户饮食历史摘要")
    health_goals: list[HealthGoalInput] = Field(default_factory=list, description="活跃健康目标")
    budget_cent: int | None = Field(None, description="本餐预算（分），如 3000 = 30元")

    # --- Context ---
    meal_type: Literal["breakfast", "lunch", "dinner", "snack", "late_night"] | None = Field(
        None, description="目标餐次（不填则根据当前时间自动推断）"
    )
    scenario: str | None = Field(
        None, description="overtime | eye_care | hair_care | caffeine_cut | energy_boost"
    )
    delivery_only: bool = Field(False, description="仅推荐可外卖配送的餐食")
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)

    # --- Dietary Constraints ---
    diet_types: list[str] = Field(default_factory=list, description="omnivore | vegetarian | vegan | keto | ...")
    allergens: list[str] = Field(default_factory=list, description="过敏源列表")
    exclude_foods: list[str] = Field(default_factory=list, description="额外排除的食物")

    # --- User Profile Snapshot ---
    daily_kcal_target: int = Field(2000, ge=800, le=6000)
    target_protein_pct: float = Field(20, ge=5, le=60)
    target_fat_pct: float = Field(30, ge=5, le=70)
    target_carbs_pct: float = Field(50, ge=5, le=80)
    activity_level: str = "sedentary"
    spice_level: int | None = Field(None, ge=0, le=5)
    oil_level: int | None = Field(None, ge=0, le=5)


# ============================================================================
# Output: MealRecommendation
# ============================================================================


class RecommendedItem(BaseModel):
    """A single recommended food/dish item."""

    food_name: str = Field(..., description="食物名称")
    serving_size_g: float | None = Field(None, description="推荐份量（克）")
    estimated_kcal: float | None = Field(None, description="预估热量 (kcal)")
    estimated_protein_g: float | None = None
    estimated_fat_g: float | None = None
    estimated_carbs_g: float | None = None
    estimated_price_cent: int | None = Field(None, description="预估价格（分）")
    reason_text: str | None = Field(None, description="推荐理由（可解释性）")
    nutrition_tags: list[str] = Field(default_factory=list, description="营养标签")
    goal_alignment: list[str] = Field(default_factory=list, description="对齐的健康目标")
    is_budget_friendly: bool = Field(False, description="是否在预算内")
    alternative: str | None = Field(None, description="备选替代食物")


class NutritionSummary(BaseModel):
    """Nutrition totals for the recommended meal."""

    total_kcal: float = 0
    total_protein_g: float = 0
    total_fat_g: float = 0
    total_carbs_g: float = 0
    total_fiber_g: float = 0
    total_price_cent: int | None = None
    within_budget: bool = True
    meal_kcal_pct: float | None = Field(None, description="占全天热量目标的百分比")


class MealRecommendation(BaseModel):
    """
    Complete next-meal recommendation output.

    Includes:
    - Recommended food items with reasoning
    - Nutrition breakdown
    - Budget analysis
    - Health goal alignment explanation
    - History-aware notes (why these foods, what's different from yesterday)
    """

    # Identity
    meal_type: str
    generated_at: datetime | None = None
    user_id: UUID | None = None

    # Core recommendation
    summary_text: str = Field(..., description="推荐摘要（给用户看的自然语言）")
    items: list[RecommendedItem] = Field(default_factory=list, description="推荐食物列表")
    nutrition: NutritionSummary = Field(default_factory=NutritionSummary)

    # Health goal alignment
    goal_alignment_score: float = Field(0, ge=0, le=100, description="健康目标对齐评分")
    goal_alignment_detail: str = Field("", description="如何对齐健康目标的解释")

    # History awareness
    history_awareness: str = Field("", description="与近期饮食的对比和变化说明")
    diversity_note: str = Field("", description="食物多样性说明")

    # Budget analysis
    budget_analysis: str = Field("", description="预算分析")
    budget_utilization_pct: float | None = Field(None, description="预算利用率%")

    # Additional
    tips: list[str] = Field(default_factory=list, description="额外建议")
    alternatives: list[RecommendedItem] = Field(default_factory=list, description="备选方案")

    # Metadata
    model_name: str = ""
    analysis_summary: dict = Field(default_factory=dict, description="内部分析摘要（调试用）")
    warnings: list[str] = Field(default_factory=list)
