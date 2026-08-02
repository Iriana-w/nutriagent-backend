"""
NutriAgent Backend — Memory Agent State.

LangGraph state definition for the memory management pipeline.

Three workflows:
- remember: intake → embed → store → link → consolidate
- recall:   embed_query → vector_search → rank → format
- profile:  aggregate → extract → structure → summarize
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.schemas.memory_agent import (
    MemoryEntry,
    MemoryEvent,
    MemorySearchResult,
    PreferenceProfile,
)


@dataclass
class MemoryAgentState:
    """State flowing through memory agent LangGraph workflows."""

    # =========================================================================
    # Input — operation routing
    # =========================================================================
    operation: str = "remember"  # remember | recall | consolidate | profile
    user_id: str = ""

    # --- remember ---
    event: MemoryEvent | None = None
    events: list[MemoryEvent] = field(default_factory=list)

    # --- recall ---
    query_text: str = ""
    query_memory_type: str | None = None
    query_top_k: int = 10
    query_min_importance: float = 0.0
    query_min_confidence: float = 0.0

    # --- consolidate ---
    similarity_threshold: float = 0.85
    max_memories: int = 1000
    min_importance_for_prune: float = 0.05

    # =========================================================================
    # Processing
    # =========================================================================
    # Embedding
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    query_embedding: list[float] = field(default_factory=list)
    content_embedding: list[float] = field(default_factory=list)

    # Normalization
    normalized_content: str = ""
    extracted_key_facts: list[dict] = field(default_factory=list)
    inferred_tags: list[str] = field(default_factory=list)
    inferred_memory_type: str = "preference"
    inferred_importance: float = 0.5

    # =========================================================================
    # Storage
    # =========================================================================
    stored_memory: MemoryEntry | None = None
    stored_memory_id: UUID | None = None
    storage_success: bool = False

    # =========================================================================
    # Retrieval
    # =========================================================================
    search_results: list[MemoryEntry] = field(default_factory=list)
    total_found: int = 0
    search_result: MemorySearchResult | None = None

    # =========================================================================
    # Consolidation
    # =========================================================================
    similar_pairs: list[tuple[UUID, UUID, float]] = field(default_factory=list)  # (id1, id2, similarity)
    merged_count: int = 0
    pruned_count: int = 0
    memories_before: int = 0
    memories_after: int = 0

    # =========================================================================
    # Profile Extraction
    # =========================================================================
    all_preference_memories: list[MemoryEntry] = field(default_factory=list)
    extracted_preferences: list[dict] = field(default_factory=list)
    preference_profile: PreferenceProfile | None = None

    # =========================================================================
    # LLM
    # =========================================================================
    raw_llm_output: str = ""
    model_name: str = ""

    # =========================================================================
    # Output
    # =========================================================================
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    output_dict: dict[str, Any] = field(default_factory=dict)
