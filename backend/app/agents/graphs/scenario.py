"""
NutriAgent Backend — Scenario Recommendation Graph.

LangGraph workflow for scenario-based recommendations:
overtime, eye_care, hair_care, caffeine_cut, energy_boost, etc.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agents.context import ContextAssembler
from app.agents.generator import Generator
from app.agents.intent import IntentClassifier
from app.agents.retriever import Retriever
from app.agents.state import RecommendationState
from app.agents.validator import Validator


def create_scenario_graph() -> StateGraph:
    """
    Build the scenario recommendation LangGraph.

    Workflow: intent → context → RAG (scenario-focused) → generate → validate → END

    Scenario recommendations include both food suggestions AND
    lifestyle/nutrition tips for the specific programmer scenario.
    """

    intent_classifier = IntentClassifier()
    context_assembler = ContextAssembler()
    retriever = Retriever()
    # Use deep model for scenario recommendations — they require more domain knowledge
    generator = Generator()
    validator = Validator()

    workflow = StateGraph(RecommendationState)

    workflow.add_node("classify_intent", intent_classifier.classify)
    workflow.add_node("assemble_context", context_assembler.assemble)
    workflow.add_node("retrieve_knowledge", retriever.retrieve)
    workflow.add_node("generate_scenario_rec", _generate_scenario)
    workflow.add_node("validate_recommendation", validator.validate)

    workflow.set_entry_point("classify_intent")
    workflow.add_edge("classify_intent", "assemble_context")
    workflow.add_edge("assemble_context", "retrieve_knowledge")
    workflow.add_edge("retrieve_knowledge", "generate_scenario_rec")
    workflow.add_edge("generate_scenario_rec", "validate_recommendation")
    workflow.add_edge("validate_recommendation", END)

    return workflow.compile()


async def _generate_scenario(state: RecommendationState) -> RecommendationState:
    """
    Custom generation for scenario recommendations.
    Injects extra scenario-specific system prompt content.
    """
    generator = Generator()

    # Add scenario-specific knowledge to the retrieved knowledge
    from app.tools.nutrition_kb import format_knowledge_for_prompt

    extra_kb = format_knowledge_for_prompt(
        scenario=state.scenario,
        include_general=False,
    )
    state.retrieved_knowledge += f"\n\n{extra_kb}"

    # Generate
    state = await generator.generate(state)

    return state


scenario_graph = create_scenario_graph()
