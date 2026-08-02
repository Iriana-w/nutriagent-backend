"""
NutriAgent Backend — Daily Plan Graph.

LangGraph workflow for full-day meal planning.
Generates 3 meals + optional snacks as a cohesive plan.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agents.context import ContextAssembler
from app.agents.generator import Generator
from app.agents.retriever import Retriever
from app.agents.state import RecommendationState
from app.agents.validator import Validator


def create_daily_plan_graph() -> StateGraph:
    """
    Build the daily meal plan LangGraph.

    Workflow: context → RAG → generate (all meals) → validate → END

    Unlike single meal, daily plan skips intent classification
    (always "daily") and generates all meals in one LLM call.
    """

    context_assembler = ContextAssembler()
    retriever = Retriever()
    generator = Generator()  # Uses deep model for complex multi-meal planning
    validator = Validator()

    workflow = StateGraph(RecommendationState)

    workflow.add_node("assemble_context", context_assembler.assemble)
    workflow.add_node("retrieve_knowledge", retriever.retrieve)
    workflow.add_node("generate_plan", _generate_daily_plan)
    workflow.add_node("validate_plan", validator.validate)

    workflow.set_entry_point("assemble_context")
    workflow.add_edge("assemble_context", "retrieve_knowledge")
    workflow.add_edge("retrieve_knowledge", "generate_plan")
    workflow.add_edge("generate_plan", "validate_plan")
    workflow.add_edge("validate_plan", END)

    return workflow.compile()


async def _generate_daily_plan(state: RecommendationState) -> RecommendationState:
    """
    Custom generation node for daily planning.
    Overrides the standard Generator prompt to produce 3-5 meals.
    """
    generator = Generator()

    # Temporarily override meal_type for the prompt
    original_meal = state.meal_type
    state.meal_type = "daily"  # Signal to the prompt builder

    state = await generator.generate(state)

    # Restore
    state.meal_type = original_meal

    return state


_daily_plan_graph = None

def get_daily_plan_graph():
    global _daily_plan_graph
    if _daily_plan_graph is None:
        _daily_plan_graph = create_daily_plan_graph()
    return _daily_plan_graph

daily_plan_graph = get_daily_plan_graph  # backward compat
