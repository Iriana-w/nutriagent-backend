"""
NutriAgent Backend — Recommendation Agent State.

LangGraph state for the enhanced next-meal recommendation pipeline.

Pipeline (6 nodes):
  analyze_history → align_goals → plan_budget → retrieve_foods → generate → validate
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.schemas.recommendation_agent import (
    HealthGoalInput,
    HistorySummary,
    MealRecommendation,
    RecommendationRequest,
)


@dataclass
class RecommendationAgentState:
    """State for the enhanced recommendation LangGraph pipeline."""

    # =========================================================================
    # Input
    # =========================================================================
    request: RecommendationRequest | None = None
    user_id: str = ""
    meal_type: str = ""
    budget_cent: int | None = None
    daily_kcal_target: int = 2000

    # =========================================================================
    # Node 1: Analyze History
    # =========================================================================
    history: HistorySummary | None = None
    recent_food_set: set[str] = field(default_factory=set)
    avoided_foods: list[str] = field(default_factory=list)  # foods to avoid based on history
    meal_pattern_insights: list[str] = field(default_factory=list)
    history_gaps: list[str] = field(default_factory=list)

    # =========================================================================
    # Node 2: Align Goals
    # =========================================================================
    health_goals: list[HealthGoalInput] = field(default_factory=list)
    goal_food_requirements: dict[str, list[str]] = field(default_factory=dict)  # goal→required nutrients/foods
    goal_avoid_foods: list[str] = field(default_factory=list)  # foods to avoid based on goals
    goal_context_prompt: str = ""  # RAG-enhanced goal context

    # =========================================================================
    # Node 3: Plan Budget
    # =========================================================================
    budget_cent_target: int | None = None
    budget_per_item_max: int | None = None
    budget_strategy: str = "balanced"  # economical | balanced | premium
    budget_analysis_text: str = ""

    # =========================================================================
    # Node 4: Retrieve Foods (RAG)
    # =========================================================================
    retrieved_knowledge: str = ""
    retrieved_foods: list[dict[str, Any]] = field(default_factory=list)
    retrieved_by_goal: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    retrieval_sources: dict[str, Any] = field(default_factory=dict)

    # =========================================================================
    # Node 5: Generate (LLM)
    # =========================================================================
    prompt_text: str = ""
    raw_llm_output: str = ""
    structured_output: dict[str, Any] = field(default_factory=dict)
    summary_text: str = ""
    items: list[dict[str, Any]] = field(default_factory=list)
    model_name: str = ""
    latency_ms: int | None = None
    total_tokens: int | None = None

    # =========================================================================
    # Node 6: Validate
    # =========================================================================
    validation_passed: bool = False
    validation_warnings: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    goal_alignment_score: float = 0.0
    budget_utilization_pct: float | None = None
    diversity_score: float = 0.0

    # =========================================================================
    # Final Output
    # =========================================================================
    final_recommendation: MealRecommendation | None = None
    output_dict: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
