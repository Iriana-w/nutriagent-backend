"""
NutriAgent Backend — Recommendation Agent.

Entry point for the enhanced next-meal recommendation agent.
Powered by three core signals: user history, health goals, and budget.

Usage:
    agent = RecommendationAgent()
    result = await agent.recommend(request)
"""

from __future__ import annotations

from datetime import datetime

from app.agents.graphs.next_meal_recommend import next_meal_recommend_graph
from app.agents.recommendation_state import RecommendationAgentState
from app.schemas.recommendation_agent import MealRecommendation, RecommendationRequest


class RecommendationAgent:
    """
    AI-powered next-meal recommendation agent.

    Takes a RecommendationRequest with three core inputs:
    1. **user_history** — recent meals, likes/dislikes, nutrition gaps
    2. **health_goals** — active health objectives with priorities
    3. **budget** — per-meal budget constraint

    Returns a MealRecommendation with:
    - Personalized food recommendations with reasoning
    - Health goal alignment scoring
    - Budget analysis and utilization
    - History-aware diversity notes
    - Alternative options
    """

    def __init__(self):
        self._graph = next_meal_recommend_graph

    async def recommend(self, request: RecommendationRequest) -> MealRecommendation:
        """
        Generate a personalized next-meal recommendation.

        Args:
            request: Full recommendation request with history, goals, budget

        Returns:
            MealRecommendation with items, nutrition, and analysis

        Raises:
            ValueError: If the request is invalid or generation fails
        """
        # Infer meal type if not provided
        meal_type = request.meal_type or self._infer_meal_type()

        # Build initial state
        initial_state = RecommendationAgentState(
            request=request,
            user_id=str(request.user_id) if request.user_id else "",
            meal_type=meal_type,
            budget_cent=request.budget_cent,
            daily_kcal_target=request.daily_kcal_target,
            health_goals=request.health_goals,
        )

        # Run the LangGraph pipeline
        result = await self._graph.ainvoke(initial_state)

        if isinstance(result, dict):
            state = RecommendationAgentState(**result)
        else:
            state = result

        if state.error:
            raise ValueError(f"Recommendation failed: {state.error}")

        if state.final_recommendation is None:
            raise ValueError("Recommendation produced no output")

        return state.final_recommendation

    async def recommend_dict(self, request_dict: dict) -> dict:
        """Run recommendation from a dict and return dict output."""
        request = RecommendationRequest(**request_dict)
        result = await self.recommend(request)
        return result.model_dump()

    @staticmethod
    def _infer_meal_type() -> str:
        """Infer meal type from current hour."""
        hour = datetime.now().hour
        if 6 <= hour < 10:
            return "breakfast"
        elif 10 <= hour < 14:
            return "lunch"
        elif 14 <= hour < 18:
            return "snack"
        elif 18 <= hour < 21:
            return "dinner"
        else:
            return "late_night"


# Singleton
recommendation_agent = RecommendationAgent()
