"""
NutriAgent Backend — Agent State Definitions.

TypedDict and dataclass state schemas for LangGraph workflows.
Each graph type has its own state definition extending the base.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, Sequence

from langgraph.graph.message import add_messages


# ============================================================================
# Base State — shared across all recommendation graphs
# ============================================================================


@dataclass
class RecommendationState:
    """Shared state for the recommendation agent workflow.

    This state flows through the 5-layer pipeline:
    intent → context → RAG → generate → validate
    """

    # --- Input ---
    user_id: str = ""
    request_type: str = "meal"  # meal | daily | weekly | scenario
    meal_type: str = ""           # breakfast | lunch | dinner | snack | late_night
    scenario: str | None = None   # overtime | eye_care | hair_care | ...
    budget_cent: int | None = None
    delivery_only: bool = False
    lat: float | None = None
    lng: float | None = None
    exclude_foods: list[str] = field(default_factory=list)
    target_date: str = ""          # ISO date string for daily/weekly planning

    # --- Layer 1: Intent ---
    intent: str = ""               # classified intent
    intent_confidence: float = 0.0

    # --- Layer 2: Context ---
    user_context: dict[str, Any] = field(default_factory=dict)
    time_context: dict[str, Any] = field(default_factory=dict)
    nutrition_gaps: list[str] = field(default_factory=list)

    # --- Layer 3: RAG ---
    retrieved_knowledge: str = ""  # concatenated nutrition knowledge
    retrieved_foods: list[dict[str, Any]] = field(default_factory=list)
    retrieved_delivery: list[dict[str, Any]] = field(default_factory=list)

    # --- Layer 4: Generation ---
    prompt_text: str = ""
    raw_llm_output: str = ""
    structured_output: dict[str, Any] = field(default_factory=dict)

    # --- Layer 5: Validation ---
    validation_passed: bool = False
    validation_warnings: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)

    # --- Final Output ---
    summary_text: str = ""
    recommendation_json: dict[str, Any] = field(default_factory=dict)
    items: list[dict[str, Any]] = field(default_factory=list)
    model_name: str = ""
    model_version: str | None = None
    template_id: str | None = None
    retrieval_sources: dict[str, Any] = field(default_factory=dict)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int | None = None

    # --- Error Handling ---
    error: str | None = None

    @property
    def is_delivery_search(self) -> bool:
        return self.delivery_only or (self.lat is not None and self.lng is not None)

    @property
    def has_user_context(self) -> bool:
        return bool(self.user_context)


# ============================================================================
# Chat State
# ============================================================================


@dataclass
class ChatState:
    """State for the conversational chat agent."""

    user_id: str = ""
    session_id: str = ""
    messages: Annotated[list, add_messages] = field(default_factory=list)
    user_context: dict[str, Any] = field(default_factory=dict)
    intent: str = ""
    response: str = ""
    error: str | None = None
