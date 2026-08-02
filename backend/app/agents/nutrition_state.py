"""
NutriAgent Backend — Nutrition Agent State.

LangGraph state definition for the diet analysis pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.schemas.nutrition_agent import (
    DimensionScore,
    FoodRecord,
    MacroBalance,
    MealTimingAnalysis,
    MicronutrientGap,
    NutritionAnalysis,
)


@dataclass
class NutritionAgentState:
    """
    State flowing through the nutrition analysis LangGraph pipeline.

    Pipeline: parse → calculate_metrics → evaluate_scoring → generate_insights → format_output
    """

    # =========================================================================
    # Input
    # =========================================================================
    food_record: FoodRecord | None = None
    food_record_dict: dict[str, Any] = field(default_factory=dict)

    # =========================================================================
    # Node 1: Parse & Validate
    # =========================================================================
    parsed_meals: list[dict[str, Any]] = field(default_factory=list)
    all_food_items: list[dict[str, Any]] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)

    # =========================================================================
    # Node 2: Calculate Metrics
    # =========================================================================
    total_kcal: float = 0.0
    total_protein_g: float = 0.0
    total_fat_g: float = 0.0
    total_carbs_g: float = 0.0
    total_fiber_g: float = 0.0
    total_sodium_mg: float = 0.0
    total_sugar_g: float = 0.0
    total_caffeine_mg: float = 0.0
    kcal_target: int = 2000
    macro_balance: MacroBalance | None = None
    meal_timing: MealTimingAnalysis | None = None
    food_variety_count: int = 0
    unique_food_names: list[str] = field(default_factory=list)
    processed_food_count: int = 0
    processed_food_pct: float = 0.0

    # Micronutrient estimates
    estimated_lutein_ug: float = 0.0
    estimated_omega3_g: float = 0.0
    estimated_vitamin_a_ug: float = 0.0
    estimated_vitamin_c_mg: float = 0.0
    estimated_calcium_mg: float = 0.0
    estimated_iron_mg: float = 0.0
    estimated_magnesium_mg: float = 0.0
    micronutrient_gaps: list[MicronutrientGap] = field(default_factory=list)

    # =========================================================================
    # Node 3: Evaluate Scoring
    # =========================================================================
    dimension_scores: list[DimensionScore] = field(default_factory=list)
    health_score_raw: float = 0.0
    health_score: float = 0.0
    health_grade: str = "C"

    # =========================================================================
    # Node 4: Generate Insights (LLM)
    # =========================================================================
    raw_llm_output: str = ""
    ai_summary: str = ""
    ai_strengths: list[str] = field(default_factory=list)
    ai_weaknesses: list[str] = field(default_factory=list)
    ai_suggestions: list[str] = field(default_factory=list)
    ai_meal_ideas: list[str] = field(default_factory=list)
    model_name: str = ""
    llm_tokens: int | None = None

    # =========================================================================
    # Node 5: Format Output
    # =========================================================================
    final_analysis: NutritionAnalysis | None = None
    output_dict: dict[str, Any] = field(default_factory=dict)

    # =========================================================================
    # Flow Control
    # =========================================================================
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    analysis_latency_ms: int | None = None
