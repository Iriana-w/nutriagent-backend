"""
NutriAgent Backend — Memory Routes.

POST   /api/v1/memory/remember       # Store a preference as vector memory
POST   /api/v1/memory/recall         # Semantic search over memories
POST   /api/v1/memory/consolidate    # Merge, decay, and prune memories
GET    /api/v1/memory/profile        # Get extracted preference profile
DELETE /api/v1/memory/{id}           # Delete a specific memory
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Path

from app.agents.memory_agent import memory_agent
from app.api.deps import CurrentUserId, DBSession
from app.schemas.memory_agent import (
    ConsolidateRequest,
    ConsolidateResult,
    MemoryEvent,
    MemoryQuery,
    MemorySearchResult,
    PreferenceProfile,
)
from app.tools.memory_store import memory_store

router = APIRouter(prefix="/memory", tags=["Memory"])


@router.post("/remember", status_code=201)
async def remember_event(
    user_id: CurrentUserId,
    event: MemoryEvent,
) -> dict:
    """
    Store a user preference as a long-term vector memory.

    The memory is:
    1. Normalized — key facts and tags extracted
    2. Embedded — converted to a 1536-dimension vector via OpenAI embeddings
    3. Stored — persisted in PostgreSQL with pgvector for semantic search

    Memory types are inferred:
    - like/dislike/prefer/avoid → preference
    - goal → goal
    - habit → summary
    - context → episode

    Event sources include:
    - explicit_feedback: user tapped 👍/👎
    - meal_record: meals logged
    - recommendation_feedback: rated a recommendation
    - conversation: mentioned in chat
    - implicit_behavior: inferred by system
    """
    # Ensure user_id matches auth
    if event.user_id != UUID(user_id):
        event.user_id = UUID(user_id)

    result = await memory_agent.remember(event)
    return result


@router.post("/recall", response_model=MemorySearchResult)
async def recall_memories(
    user_id: CurrentUserId,
    db: DBSession,
    query: MemoryQuery,
) -> MemorySearchResult:
    """
    Search user's long-term memories using keyword matching.
    """
    import traceback
    from sqlalchemy import text as sa_text
    try:
        if query.user_id != UUID(user_id):
            query.user_id = UUID(user_id)

        # Use keyword search to avoid pgvector dependency issues
        conditions = ["user_id = :uid"]
        params = {"uid": str(query.user_id), "q": f"%{query.query_text}%", "limit": query.top_k}

        if query.memory_type:
            conditions.append("memory_type = :mtype")
            params["mtype"] = query.memory_type
        if query.min_importance > 0:
            conditions.append("importance >= :min_imp")
            params["min_imp"] = query.min_importance

        where = " AND ".join(conditions)
        sql = f"""
            SELECT id, user_id, memory_type, title, content, key_facts,
                   importance, confidence, access_count, decay_factor,
                   source, source_id, created_at, updated_at, expires_at,
                   0.5 as similarity_score
            FROM agent_memories
            WHERE {where} AND (title ILIKE :q OR content ILIKE :q)
            ORDER BY importance DESC, created_at DESC
            LIMIT :limit
        """

        result = await db.execute(sa_text(sql), params)
        rows = result.fetchall()

        from app.schemas.memory_agent import MemoryEntry, MemorySearchResult
        from datetime import datetime

        entries = []
        for r in rows:
            entries.append(MemoryEntry(
                id=r.id, user_id=r.user_id,
                memory_type=r.memory_type if isinstance(r.memory_type, str) else r.memory_type.value,
                title=r.title, content=r.content, key_facts=r.key_facts or [],
                importance=float(r.importance or 0.5), confidence=float(r.confidence or 1.0),
                access_count=r.access_count or 0, decay_factor=float(r.decay_factor or 1.0),
                source=r.source or "", source_id=r.source_id,
                similarity_score=float(r.similarity_score or 0.5),
                created_at=r.created_at, updated_at=r.updated_at, expires_at=r.expires_at,
            ))

        return MemorySearchResult(
            query_text=query.query_text, results=entries,
            total_found=len(entries), search_type="keyword",
            retrieved_at=datetime.utcnow(),
        )
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail={"error": type(e).__name__, "message": str(e), "traceback": traceback.format_exc()})


@router.post("/consolidate", response_model=ConsolidateResult)
async def consolidate_memories(
    user_id: CurrentUserId,
    request: ConsolidateRequest,
) -> ConsolidateResult:
    """
    Consolidate user's long-term memories:

    1. **Apply decay** — Ebbinghaus forgetting curve
       - Normal memories: half-life 30 days
       - Important memories (importance > 0.7): half-life 90 days

    2. **Merge similar** — memories with cosine similarity > threshold
       are merged into one, combining key facts and updating importance

    3. **Prune stale** — remove heavily decayed + low-importance memories
       Also enforces a max memory count per user

    4. **Extract profile** — LLM-powered structured preference extraction
       from all remaining preference memories

    Returns the updated PreferenceProfile.
    """
    if request.user_id != UUID(user_id):
        request.user_id = UUID(user_id)

    result = await memory_agent.consolidate(request)
    return result


@router.get("/profile", response_model=PreferenceProfile)
async def get_preference_profile(
    user_id: CurrentUserId,
) -> PreferenceProfile:
    """
    Get the current extracted preference profile.

    Built by aggregating all preference-type memories and
    using LLM to extract structured preferences:
    - Taste preferences (spice, sweet, oil levels)
    - Liked / disliked / craved / avoided foods
    - Favorite and avoided cuisines
    - Cooking preferences and meal timing patterns
    - Contextual preferences (e.g., "prefers light food when working late")
    - Narrative summary in natural language
    """
    profile = await memory_agent.get_profile(UUID(user_id))
    return profile


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(
    user_id: CurrentUserId,
    memory_id: UUID = Path(..., description="Memory ID to delete"),
) -> None:
    """Delete a specific memory entry."""
    await memory_store.delete_memory(memory_id)


@router.delete("/user/{target_user_id}", status_code=200)
async def delete_user_memories(
    user_id: CurrentUserId,
    target_user_id: UUID = Path(...),
    memory_type: str | None = None,
) -> dict:
    """Delete all (or type-filtered) memories for a user. Admin only."""
    count = await memory_store.delete_user_memories(target_user_id, memory_type)
    return {"deleted_count": count, "user_id": str(target_user_id)}
