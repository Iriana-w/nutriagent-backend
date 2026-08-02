"""
NutriAgent Backend — Nutrition Agent.

Entry point for the diet analysis agent.
Wraps the LangGraph nutrition_analysis_graph with a clean interface.

Usage:
    agent = NutritionAgent()
    result = await agent.analyze(food_record)
"""

from __future__ import annotations

from app.agents.graphs.nutrition_analysis import nutrition_analysis_graph
from app.agents.nutrition_state import NutritionAgentState
from app.schemas.nutrition_agent import FoodRecord, NutritionAnalysis


class NutritionAgent:
    """
    AI-powered diet analysis agent.

    Takes a FoodRecord (one day's meals with nutritional data)
    and returns a comprehensive NutritionAnalysis with:
    - Multi-dimensional health scoring (0-100)
    - Macro/micro nutrient analysis
    - Meal timing evaluation
    - Food quality & variety assessment
    - Programmer-specific health factors
    - AI-generated personalized insights & suggestions
    """

    def __init__(self):
        self._graph = nutrition_analysis_graph

    async def analyze(self, food_record: FoodRecord) -> NutritionAnalysis:
        """
        Run the full nutrition analysis pipeline on a FoodRecord.

        Args:
            food_record: Complete food record for a single day

        Returns:
            NutritionAnalysis with health score, dimension scores, and AI insights

        Raises:
            ValueError: If the FoodRecord is invalid
        """
        initial_state = NutritionAgentState(food_record=food_record)

        result = await self._graph.ainvoke(initial_state)

        # result is a NutritionAgentState (dict when ainvoke returns)
        if isinstance(result, dict):
            state = NutritionAgentState(**result)
        else:
            state = result

        if state.error:
            raise ValueError(f"Nutrition analysis failed: {state.error}")

        if state.final_analysis is None:
            raise ValueError("Nutrition analysis produced no output")

        return state.final_analysis

    async def analyze_dict(self, food_record_dict: dict) -> dict:
        """
        Run analysis from a dict (e.g., from API JSON body).
        Returns the output as a dict for direct JSON serialization.
        """
        food_record = FoodRecord(**food_record_dict)
        analysis = await self.analyze(food_record)
        return analysis.model_dump()


# Singleton
nutrition_agent = NutritionAgent()
