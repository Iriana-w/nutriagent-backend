"""
NutriAgent Backend — Memory Agent.

Entry point for the long-term user preference memory system.
Uses pgvector for semantic vector storage and retrieval.

Three core operations:
- remember(event): Store a new preference/feedback as a vector memory
- recall(query): Semantic search over user's long-term memories
- consolidate(user_id): Merge similar memories, apply decay, extract profile
"""

from __future__ import annotations

from uuid import UUID

from app.agents.memory_state import MemoryAgentState
from app.agents.graphs.memory_management import (
    get_memory_graph,
    normalize_event,
    embed_content,
    store_memory_node,
    embed_query,
    vector_search,
    format_search_results,
    apply_decay,
    find_and_merge,
    prune_memories,
    extract_profile_node,
)
from app.schemas.memory_agent import (
    ConsolidateRequest,
    ConsolidateResult,
    MemoryEvent,
    MemoryQuery,
    MemorySearchResult,
    PreferenceProfile,
)


class MemoryAgent:
    """
    AI-powered long-term memory agent for user preferences.

    Uses pgvector (vector database) to:
    - Store preference memories as 1536-dimension embeddings
    - Retrieve semantically similar memories via cosine similarity
    - Consolidate and merge related memories
    - Apply Ebbinghaus forgetting curve for memory decay
    - Extract structured preference profiles

    Features:
    - Embedding generation via OpenAI text-embedding-3-small
    - pgvector <=> operator for cosine distance search
    - Automatic key-fact extraction from unstructured events
    - LLM-powered preference profile generation
    """

    def __init__(self):
        self._graph = None  # Compiled on first use via _get_graph()

    def _get_graph(self):
        if self._graph is None:
            self._graph = get_memory_graph()
        return self._graph

    # =========================================================================
    # REMEMBER
    # =========================================================================

    async def remember(self, event: MemoryEvent) -> dict:
        """
        Store a user preference as a long-term vector memory.

        Pipeline: normalize → embed → store

        Args:
            event: The memory event to store

        Returns:
            dict with stored memory id and metadata
        """
        state = MemoryAgentState(
            operation="remember",
            user_id=str(event.user_id),
            event=event,
        )

        state = await normalize_event(state)
        if state.error:
            return {"error": state.error}

        state = await embed_content(state)
        if state.error:
            return {"error": state.error}

        state = await store_memory_node(state)
        if state.error:
            return {"error": state.error}

        return {
            "memory_id": str(state.stored_memory_id),
            "title": event.title,
            "memory_type": state.inferred_memory_type,
            "importance": state.inferred_importance,
            "success": state.storage_success,
            "warnings": state.warnings,
        }

    async def remember_batch(self, events: list[MemoryEvent]) -> list[dict]:
        """Store multiple memory events."""
        results = []
        for event in events:
            result = await self.remember(event)
            results.append(result)
        return results

    # =========================================================================
    # RECALL
    # =========================================================================

    async def recall(self, query: MemoryQuery) -> MemorySearchResult:
        """
        Search user's long-term memories semantically.

        Pipeline: embed_query → vector_search → format

        Args:
            query: The search query with user_id, text, and filters

        Returns:
            MemorySearchResult with ranked, similarity-scored memories
        """
        state = MemoryAgentState(
            operation="recall",
            user_id=str(query.user_id),
            query_text=query.query_text,
            query_memory_type=query.memory_type,
            query_top_k=query.top_k,
            query_min_importance=query.min_importance,
            query_min_confidence=query.min_confidence,
        )

        state = await embed_query(state)
        if state.error:
            raise ValueError(state.error)

        state = await vector_search(state)
        if state.error:
            raise ValueError(state.error)

        state = await format_search_results(state)
        return state.search_result

    # =========================================================================
    # CONSOLIDATE
    # =========================================================================

    async def consolidate(self, request: ConsolidateRequest) -> ConsolidateResult:
        """
        Consolidate user memories: apply decay, merge similar, prune stale.

        Pipeline: apply_decay → find_merge → prune → extract_profile

        Args:
            request: Consolidation parameters

        Returns:
            ConsolidateResult with counts and updated profile
        """
        state = MemoryAgentState(
            operation="consolidate",
            user_id=str(request.user_id),
            similarity_threshold=request.similarity_threshold,
            max_memories=request.max_memories,
            min_importance_for_prune=request.min_importance,
        )

        state = await apply_decay(state)
        state = await find_and_merge(state)
        state = await prune_memories(state)
        state = await extract_profile_node(state)

        if state.error:
            raise ValueError(state.error)

        return ConsolidateResult(
            user_id=request.user_id,
            memories_before=state.memories_before,
            memories_after=state.memories_after,
            merged_count=state.merged_count,
            pruned_count=state.pruned_count,
            new_profile=state.preference_profile,
        )

    # =========================================================================
    # PROFILE
    # =========================================================================

    async def get_profile(self, user_id: UUID) -> PreferenceProfile:
        """
        Get the current extracted preference profile for a user.
        Runs consolidation lite (extract only, no prune).
        """
        state = MemoryAgentState(
            operation="consolidate",
            user_id=str(user_id),
        )

        state = await extract_profile_node(state)
        if state.error:
            raise ValueError(state.error)
        if state.preference_profile is None:
            raise ValueError("Failed to extract profile")

        return state.preference_profile

    async def get_profile_dict(self, user_id: UUID) -> dict:
        """Get preference profile as dict."""
        profile = await self.get_profile(user_id)
        return profile.model_dump()


# Singleton
memory_agent = MemoryAgent()
