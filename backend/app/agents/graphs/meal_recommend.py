"""
NutriAgent Backend — Meal Recommendation Graph.

LangGraph workflow for single meal recommendation:
intent → context → RAG → generate → validate → output
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agents.context import ContextAssembler
from app.agents.generator import Generator
from app.agents.intent import IntentClassifier
from app.agents.retriever import Retriever
from app.agents.state import RecommendationState
from app.agents.validator import Validator


def create_meal_recommend_graph() -> StateGraph:
    """
    Build and compile the meal recommendation LangGraph.

    Pipeline:
    ┌──────────┐    ┌───────────┐    ┌──────────┐    ┌───────────┐    ┌──────────┐
    │  intent  │───→│  context  │───→│ retriever│───→│ generator │───→│validator │───→ END
    └──────────┘    └───────────┘    └──────────┘    └───────────┘    └──────────┘
    """

    # Instantiate nodes
    intent_classifier = IntentClassifier()
    context_assembler = ContextAssembler()
    retriever = Retriever()
    generator = Generator()
    validator = Validator()

    # Build graph
    workflow = StateGraph(RecommendationState)

    # Add nodes
    workflow.add_node("classify_intent", intent_classifier.classify)
    workflow.add_node("assemble_context", context_assembler.assemble)
    workflow.add_node("retrieve_knowledge", retriever.retrieve)
    workflow.add_node("generate_recommendation", generator.generate)
    workflow.add_node("validate_recommendation", validator.validate)

    # Define edges (linear pipeline)
    workflow.set_entry_point("classify_intent")
    workflow.add_edge("classify_intent", "assemble_context")
    workflow.add_edge("assemble_context", "retrieve_knowledge")
    workflow.add_edge("retrieve_knowledge", "generate_recommendation")
    workflow.add_edge("generate_recommendation", "validate_recommendation")

    # Conditional edge: retry on validation failure (max 1 retry)
    workflow.add_conditional_edges(
        "validate_recommendation",
        _should_retry,
        {
            "retry": "generate_recommendation",
            "end": END,
        },
    )

    return workflow.compile()


def _should_retry(state: RecommendationState) -> str:
    """Decide whether to retry generation on validation failure."""
    if state.error:
        return "end"
    if state.validation_passed:
        return "end"
    if not state.items:
        return "end"
    prev = getattr(state, '_prev_errors', None)
    if state.validation_errors and state.validation_errors != prev:
        object.__setattr__(state, '_prev_errors', list(state.validation_errors))
        return "retry"
    return "end"


# Create and export the compiled graph
meal_recommend_graph = create_meal_recommend_graph()
