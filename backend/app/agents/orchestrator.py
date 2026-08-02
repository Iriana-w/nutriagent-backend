"""
NutriAgent Backend — Agent Orchestrator.

Routes requests to the appropriate LangGraph workflow and manages
the execution of the recommendation pipeline.
"""

from __future__ import annotations

from app.agents.graphs.daily_plan import create_daily_plan_graph
from app.agents.graphs.meal_recommend import create_meal_recommend_graph
from app.agents.graphs.scenario import create_scenario_graph
from app.agents.state import RecommendationState


class AgentOrchestrator:
    """
    Central orchestrator for AI recommendation workflows.

    Routes user requests to the correct LangGraph pipeline:
    - meal_recommend: single meal recommendation
    - daily_plan: full day meal planning
    - scenario: scenario-based recommendations
    """

    def __init__(self):
        self._meal_graph = None
        self._daily_graph = None
        self._scenario_graph = None

    @property
    def meal_graph(self):
        if self._meal_graph is None:
            self._meal_graph = create_meal_recommend_graph()
        return self._meal_graph

    @property
    def daily_graph(self):
        if self._daily_graph is None:
            self._daily_graph = create_daily_plan_graph()
        return self._daily_graph

    @property
    def scenario_graph(self):
        if self._scenario_graph is None:
            self._scenario_graph = create_scenario_graph()
        return self._scenario_graph

    async def run_meal_recommendation(
        self,
        user_id: str,
        meal_type: str,
        scenario: str | None = None,
        budget_cent: int | None = None,
        delivery_only: bool = False,
        lat: float | None = None,
        lng: float | None = None,
        exclude_foods: list[str] | None = None,
    ) -> dict:
        """Run a single meal recommendation workflow."""
        initial_state = RecommendationState(
            user_id=user_id,
            request_type="meal",
            meal_type=meal_type,
            scenario=scenario,
            budget_cent=budget_cent,
            delivery_only=delivery_only,
            lat=lat,
            lng=lng,
            exclude_foods=exclude_foods or [],
        )

        result = await self.meal_graph.ainvoke(initial_state)
        return self._extract_result(result)

    async def run_daily_plan(
        self,
        user_id: str,
        target_date: str = "",
        scenario: str | None = None,
        budget_cent: int | None = None,
        delivery_only: bool = False,
        lat: float | None = None,
        lng: float | None = None,
        exclude_foods: list[str] | None = None,
    ) -> dict:
        """Run a daily meal plan workflow."""
        initial_state = RecommendationState(
            user_id=user_id,
            request_type="daily",
            target_date=str(target_date),
            scenario=scenario,
            budget_cent=budget_cent,
            delivery_only=delivery_only,
            lat=lat,
            lng=lng,
            exclude_foods=exclude_foods or [],
        )

        result = await self.daily_graph.ainvoke(initial_state)
        return self._extract_result(result)

    async def run_scenario_recommendation(
        self,
        user_id: str,
        scenario: str,
        meal_type: str | None = None,
    ) -> dict:
        """Run a scenario-based recommendation workflow."""
        initial_state = RecommendationState(
            user_id=user_id,
            request_type="scenario",
            scenario=scenario,
            meal_type=meal_type or "",
        )

        result = await self.scenario_graph.ainvoke(initial_state)
        return self._extract_result(result)

    def _extract_result(self, result: RecommendationState | dict) -> dict:
        """Extract the output dict from the final state."""
        if isinstance(result, dict):
            state = result
        else:
            state = result.__dict__ if hasattr(result, '__dict__') else result

        # If it's a state object
        if hasattr(result, 'summary_text'):
            return {
                "model_name": getattr(result, 'model_name', 'unknown'),
                "model_version": getattr(result, 'model_version', None),
                "template_id": getattr(result, 'template_id', None),
                "retrieval_sources": getattr(result, 'retrieval_sources', {}),
                "recommendation_json": getattr(result, 'recommendation_json', {}),
                "summary_text": getattr(result, 'summary_text', ''),
                "items": getattr(result, 'items', []),
                "prompt_tokens": getattr(result, 'prompt_tokens', None),
                "completion_tokens": getattr(result, 'completion_tokens', None),
                "total_tokens": getattr(result, 'total_tokens', None),
                "latency_ms": getattr(result, 'latency_ms', None),
                "validation_passed": getattr(result, 'validation_passed', False),
                "validation_warnings": getattr(result, 'validation_warnings', []),
                "validation_errors": getattr(result, 'validation_errors', []),
            }
        return state


# Singleton
_orchestrator: AgentOrchestrator | None = None


def get_orchestrator() -> AgentOrchestrator:
    """Get the global orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator
