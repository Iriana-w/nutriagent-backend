"""
NutriAgent Backend — Memory Management Graph.

LangGraph workflows for long-term user preference memory.

Three workflows orchestrated by the 'operation' field:
1. remember:  normalize → embed → store → (optional) link → (optional) consolidate
2. recall:    embed_query → vector_search → rank → format
3. consolidate: apply_decay → find_similar → merge → prune → extract_profile
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from langgraph.graph import END, StateGraph

from app.agents.base import BaseAgent
from app.agents.memory_state import MemoryAgentState
from app.schemas.memory_agent import MemoryEntry, MemorySearchResult, PreferenceProfile, ExtractedPreference
from app.tools.embedding import embedding_gen
from app.tools.memory_store import memory_store


# ============================================================================
# REMEMBER workflow nodes
# ============================================================================


async def normalize_event(state: MemoryAgentState) -> MemoryAgentState:
    """
    Normalize the raw memory event: extract key facts, infer tags,
    determine memory type and importance from the event.
    """
    event = state.event
    if not event:
        state.error = "No MemoryEvent provided"
        return state

    # Build normalized content
    parts = [f"[{event.event_type}]"]

    if event.food_name:
        parts.append(f"食物: {event.food_name}")
    if event.category:
        parts.append(f"类别: {event.category}")

    parts.append(event.content)

    if event.tags:
        parts.append(f"标签: {', '.join(event.tags)}")

    state.normalized_content = " ".join(parts)

    # Auto-generate title if empty
    if not event.title:
        food_ref = f"关于「{event.food_name}」的" if event.food_name else ""
        type_labels = {
            "like": f"{food_ref}喜欢",
            "dislike": f"{food_ref}不喜欢",
            "prefer": f"{food_ref}偏好",
            "avoid": f"{food_ref}避免",
            "crave": f"{food_ref}渴望",
            "tired_of": f"{food_ref}厌倦",
            "goal": "健康目标变更",
            "habit": "饮食习惯",
            "context": "场景偏好",
        }
        state.event.title = type_labels.get(event.event_type, "偏好记录")

    # Map event_type to memory_type
    type_mapping = {
        "goal": "goal",
        "habit": "summary",
        "context": "episode",
    }
    state.inferred_memory_type = type_mapping.get(event.event_type, "preference")

    # Infer importance from signal
    importance = event.importance
    if event.event_type in ("like", "dislike", "prefer", "avoid"):
        importance = max(importance, 0.6)  # explicit preferences are important
    if event.event_type == "goal":
        importance = max(importance, 0.8)  # health goals are very important
    state.inferred_importance = min(1.0, importance)

    # Extract key facts
    state.extracted_key_facts = _extract_facts(event)

    # Infer tags
    state.inferred_tags = list(set(event.tags + _infer_tags(event)))

    return state


def _extract_facts(event) -> list[dict]:
    """Extract structured key facts from a memory event."""
    facts = []

    if event.food_name:
        facts.append({
            "type": "food",
            "value": event.food_name,
            "sentiment": event.event_type,
            "food_id": str(event.food_id) if event.food_id else None,
        })

    if event.category:
        facts.append({"type": "category", "value": event.category})

    for tag in event.tags:
        facts.append({"type": "tag", "value": tag})

    # Extract context facts
    for key, value in (event.context or {}).items():
        if isinstance(value, (str, int, float, bool)):
            facts.append({"type": f"context_{key}", "value": str(value)})

    return facts


def _infer_tags(event) -> list[str]:
    """Infer tags from the event content and type."""
    tags = [event.event_type]

    content_lower = event.content.lower()
    if any(w in content_lower for w in ["辣", "麻辣", "火锅", "川"]):
        tags.append("spicy")
    if any(w in content_lower for w in ["甜", "糖", "蛋糕", "奶茶"]):
        tags.append("sweet")
    if any(w in content_lower for w in ["健康", "轻食", "沙拉", "低卡"]):
        tags.append("healthy")
    if any(w in content_lower for w in ["外卖", "方便", "快捷"]):
        tags.append("convenience")
    if any(w in content_lower for w in ["加班", "熬夜", "赶项目"]):
        tags.append("overtime")
    if any(w in content_lower for w in ["早餐", "午饭", "晚餐", "夜宵"]):
        tags.append("meal_timing")
    if any(w in content_lower for w in ["贵", "便宜", "省钱", "性价比"]):
        tags.append("budget")

    return tags


async def embed_content(state: MemoryAgentState) -> MemoryAgentState:
    """Generate vector embedding for the memory content."""
    if state.error:
        return state

    try:
        embed_text = f"{state.event.title}\n{state.normalized_content}"
        state.content_embedding = await embedding_gen.embed_text(embed_text)
        state.embedding_model = embedding_gen.model
        state.embedding_dim = len(state.content_embedding)
    except Exception as e:
        state.warnings.append(f"Embedding generation failed: {e}")
        # Continue without embedding — will fall back to keyword search
        state.content_embedding = []

    return state


async def store_memory_node(state: MemoryAgentState) -> MemoryAgentState:
    """Persist the memory to pgvector."""
    if state.error:
        return state

    event = state.event
    try:
        memory = await memory_store.store_memory(
            user_id=event.user_id,
            memory_type=state.inferred_memory_type,
            title=event.title,
            content=state.normalized_content,
            embedding=state.content_embedding if state.content_embedding else None,
            key_facts=state.extracted_key_facts,
            importance=state.inferred_importance,
            confidence=event.confidence,
            source=event.source,
            source_id=event.source_id,
            tags=state.inferred_tags,
        )
        state.stored_memory_id = memory.id
        state.storage_success = True

        state.stored_memory = MemoryEntry(
            id=memory.id,
            user_id=memory.user_id,
            memory_type=memory.memory_type.value,
            title=memory.title,
            content=memory.content,
            key_facts=memory.key_facts or [],
            importance=float(memory.importance),
            confidence=float(memory.confidence),
            source=memory.source,
            source_id=memory.source_id,
            created_at=memory.created_at,
        )
    except Exception as e:
        state.error = f"Failed to store memory: {e}"

    return state


# ============================================================================
# RECALL workflow nodes
# ============================================================================


async def embed_query(state: MemoryAgentState) -> MemoryAgentState:
    """Generate embedding for the search query."""
    if state.error:
        return state

    if not state.query_text:
        state.error = "No query text provided for recall"
        return state

    try:
        state.query_embedding = await embedding_gen.embed_text(state.query_text)
    except Exception as e:
        state.warnings.append(f"Query embedding failed: {e}")

    return state


async def vector_search(state: MemoryAgentState) -> MemoryAgentState:
    """Perform pgvector semantic search."""
    if state.error:
        return state

    try:
        results = await memory_store.search_semantic(
            user_id=uuid.UUID(state.user_id),
            query_text=state.query_text,
            query_embedding=state.query_embedding if state.query_embedding else None,
            memory_type=state.query_memory_type,
            min_importance=state.query_min_importance,
            min_confidence=state.query_min_confidence,
            top_k=state.query_top_k,
        )

        state.search_results = [
            MemoryEntry(
                id=r["id"],
                user_id=r["user_id"],
                memory_type=r["memory_type"],
                title=r["title"],
                content=r["content"],
                key_facts=r["key_facts"],
                importance=r["importance"],
                confidence=r["confidence"],
                access_count=r["access_count"],
                last_accessed_at=r["last_accessed_at"],
                decay_factor=r["decay_factor"],
                source=r["source"],
                source_id=r["source_id"],
                similarity_score=r["similarity_score"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                expires_at=r["expires_at"],
            )
            for r in results
        ]
        state.total_found = len(state.search_results)
    except Exception as e:
        state.error = f"Memory search failed: {e}"

    return state


async def format_search_results(state: MemoryAgentState) -> MemoryAgentState:
    """Format search results into a MemorySearchResult."""
    state.search_result = MemorySearchResult(
        query_text=state.query_text,
        results=state.search_results,
        total_found=state.total_found,
        search_type="semantic",
        retrieved_at=datetime.utcnow(),
    )
    state.output_dict = state.search_result.model_dump()
    return state


# ============================================================================
# CONSOLIDATE workflow nodes
# ============================================================================


async def apply_decay(state: MemoryAgentState) -> MemoryAgentState:
    """Apply Ebbinghaus decay to all user memories."""
    if state.error:
        return state

    user_id = uuid.UUID(state.user_id)

    state.memories_before = await memory_store.count_memories(user_id)

    updated = await memory_store.apply_decay(user_id)
    state.warnings.append(f"Decay applied to {updated} memories")

    return state


async def find_and_merge(state: MemoryAgentState) -> MemoryAgentState:
    """Find similar memories and merge them."""
    if state.error:
        return state

    user_id = uuid.UUID(state.user_id)

    similar = await memory_store.find_similar_memories(
        user_id, similarity_threshold=state.similarity_threshold
    )
    state.similar_pairs = similar

    for id1, id2, sim in similar:
        try:
            survivor = await memory_store.merge_memories(id1, id2)
            if survivor:
                state.merged_count += 1
        except Exception as e:
            state.warnings.append(f"Merge failed for {id1}+{id2}: {e}")

    return state


async def prune_memories(state: MemoryAgentState) -> MemoryAgentState:
    """Prune low-importance, heavily decayed memories."""
    if state.error:
        return state

    user_id = uuid.UUID(state.user_id)

    state.pruned_count = await memory_store.prune_low_importance(
        user_id,
        min_importance=state.min_importance_for_prune,
        max_memories=state.max_memories,
    )
    state.memories_after = await memory_store.count_memories(user_id)

    return state


async def extract_profile_node(state: MemoryAgentState) -> MemoryAgentState:
    """
    Extract a structured PreferenceProfile from all user's preference memories.
    Uses LLM to consolidate and structure preferences.
    """
    if state.error:
        return state

    user_id = uuid.UUID(state.user_id)

    # Get all preferences
    all_prefs = await memory_store.get_all_preferences(user_id)
    state.all_preference_memories = [
        MemoryEntry(
            id=p["id"], user_id=user_id,
            memory_type="preference", title=p["title"],
            content=p["content"], key_facts=p["key_facts"],
            importance=p["importance"], confidence=p["confidence"],
            decay_factor=p["decay_factor"],
            source=p["source"], created_at=p["created_at"],
        )
        for p in all_prefs
    ]

    if not all_prefs:
        # No preferences yet — return empty profile
        state.preference_profile = PreferenceProfile(
            user_id=user_id,
            generated_at=datetime.utcnow(),
            total_memories=0,
            narrative_summary="暂无长期偏好数据。继续使用NutriAgent，我会逐渐了解你的口味！",
        )
        state.output_dict = state.preference_profile.model_dump()
        return state

    # Build prompt for LLM-based preference extraction
    agent = BaseAgent.get_deep_model()

    # Prepare memory summaries for the LLM
    memory_summaries = []
    for m in all_prefs[:100]:  # top 100 most important
        facts_str = json.dumps(m["key_facts"][:5], ensure_ascii=False)
        memory_summaries.append(
            f"- [{m['title']}] (importance={m['importance']:.2f}, "
            f"confidence={m['confidence']:.2f}) {m['content'][:200]}"
        )

    system_prompt = """你是一个用户偏好分析专家。从用户的长期记忆记录中提取结构化的饮食偏好画像。

## 提取类别
- liked_foods: 用户明确喜欢/点赞的食物
- disliked_foods: 用户明确不喜欢/踩过的食物
- craved_foods: 用户渴望/反复提到的食物
- avoided_foods: 用户主动避免的食物（过敏、忌口等）
- favorite_cuisines: 喜欢的菜系（川菜、日料、西餐等）
- avoided_cuisines: 避免的菜系
- cooking_preferences: 烹饪方式偏好（蒸、煮、炒、炸等）
- meal_timing_patterns: 用餐时间模式
- budget_preference: 预算偏好
- contextual_preferences: 场景相关偏好（如"加班时吃轻食"）

## 每条偏好格式
{"category": "类别", "key": "键", "value": "值", "confidence": 0.8}

请以 JSON 格式返回。"""

    user_prompt = f"""用户共有 {len(all_prefs)} 条长期偏好记忆。以下是重要性最高的记忆：

{chr(10).join(memory_summaries[:80])}

请提取该用户的完整饮食偏好画像。返回 JSON：
{{
  "spice_level": null,
  "sweet_level": null,
  "oil_level": null,
  "liked_foods": [...],
  "disliked_foods": [...],
  "craved_foods": [...],
  "avoided_foods": [...],
  "favorite_cuisines": [...],
  "avoided_cuisines": [...],
  "cooking_preferences": [...],
  "meal_timing_patterns": [...],
  "contextual_preferences": [...],
  "narrative_summary": "用2-3句话自然语言描述该用户的饮食偏好",
  "profile_confidence": 0.0
}}
"""

    try:
        response = await agent.invoke_llm(system_prompt, user_prompt, response_format="json")
        parsed = agent.parse_json_response(response)

        state.preference_profile = PreferenceProfile(
            user_id=user_id,
            generated_at=datetime.utcnow(),
            spice_level=parsed.get("spice_level"),
            sweet_level=parsed.get("sweet_level"),
            oil_level=parsed.get("oil_level"),
            liked_foods=[
                ExtractedPreference(category="food", key=p["key"], value=p.get("value", "like"),
                                    confidence=p.get("confidence", 0.7))
                for p in parsed.get("liked_foods", [])
            ],
            disliked_foods=[
                ExtractedPreference(category="food", key=p["key"], value="dislike",
                                    confidence=p.get("confidence", 0.7))
                for p in parsed.get("disliked_foods", [])
            ],
            craved_foods=[
                ExtractedPreference(category="food", key=p["key"], value="crave",
                                    confidence=p.get("confidence", 0.7))
                for p in parsed.get("craved_foods", [])
            ],
            avoided_foods=[
                ExtractedPreference(category="food", key=p["key"], value="avoid",
                                    confidence=p.get("confidence", 0.7))
                for p in parsed.get("avoided_foods", [])
            ],
            favorite_cuisines=[
                ExtractedPreference(category="cuisine", key=p["key"], value=p.get("value", "like"),
                                    confidence=p.get("confidence", 0.7))
                for p in parsed.get("favorite_cuisines", [])
            ],
            avoided_cuisines=[
                ExtractedPreference(category="cuisine", key=p["key"], value="avoid",
                                    confidence=p.get("confidence", 0.7))
                for p in parsed.get("avoided_cuisines", [])
            ],
            cooking_preferences=[
                ExtractedPreference(category="cooking", key=p["key"], value=p.get("value", ""),
                                    confidence=p.get("confidence", 0.7))
                for p in parsed.get("cooking_preferences", [])
            ],
            meal_timing_patterns=[
                ExtractedPreference(category="timing", key=p["key"], value=p.get("value", ""),
                                    confidence=p.get("confidence", 0.7))
                for p in parsed.get("meal_timing_patterns", [])
            ],
            contextual_preferences=[
                ExtractedPreference(category="context", key=p["key"], value=p.get("value", ""),
                                    confidence=p.get("confidence", 0.7))
                for p in parsed.get("contextual_preferences", [])
            ],
            total_memories=len(all_prefs),
            total_preferences_extracted=len(parsed.get("liked_foods", []))
                                      + len(parsed.get("disliked_foods", [])),
            profile_confidence=parsed.get("profile_confidence", 0.7),
            narrative_summary=parsed.get("narrative_summary", ""),
        )
    except Exception as e:
        state.warnings.append(f"LLM profile extraction failed: {e}")
        # Build basic profile from key facts
        state.preference_profile = _build_basic_profile(user_id, all_prefs)

    state.output_dict = state.preference_profile.model_dump()
    state.model_name = agent.model_name

    return state


def _build_basic_profile(user_id, all_prefs: list[dict]) -> PreferenceProfile:
    """Build a basic preference profile from key facts without LLM."""
    liked = []
    disliked = []

    for m in all_prefs:
        for fact in m.get("key_facts", []):
            if fact.get("type") == "food":
                sentiment = fact.get("sentiment", "")
                if sentiment in ("like", "prefer", "crave"):
                    liked.append(ExtractedPreference(
                        category="food", key=fact.get("value", ""),
                        value=sentiment, confidence=m["confidence"],
                    ))
                elif sentiment in ("dislike", "avoid", "tired_of"):
                    disliked.append(ExtractedPreference(
                        category="food", key=fact.get("value", ""),
                        value=sentiment, confidence=m["confidence"],
                    ))

    return PreferenceProfile(
        user_id=user_id,
        generated_at=datetime.utcnow(),
        liked_foods=liked,
        disliked_foods=disliked,
        total_memories=len(all_prefs),
        total_preferences_extracted=len(liked) + len(disliked),
        profile_confidence=min(0.9, len(all_prefs) / 50),
        narrative_summary=f"该用户有 {len(all_prefs)} 条偏好记录。喜欢 {len(liked)} 种食物，不喜欢 {len(disliked)} 种。",
    )


# ============================================================================
# Graph Construction
# ============================================================================


def create_memory_graph() -> StateGraph:
    """
    Build the memory management LangGraph.

    Routes to different sub-graphs based on state.operation:
    - remember: normalize → embed → store → END
    - recall: embed_query → vector_search → format → END
    - consolidate: apply_decay → find_merge → prune → extract_profile → END
    """

    workflow = StateGraph(MemoryAgentState)

    # Add all nodes
    workflow.add_node("normalize_event", normalize_event)
    workflow.add_node("embed_content", embed_content)
    workflow.add_node("store_memory", store_memory_node)
    workflow.add_node("embed_query", embed_query)
    workflow.add_node("vector_search", vector_search)
    workflow.add_node("format_results", format_search_results)
    workflow.add_node("apply_decay", apply_decay)
    workflow.add_node("find_and_merge", find_and_merge)
    workflow.add_node("prune_memories", prune_memories)
    workflow.add_node("extract_profile", extract_profile_node)

    # Entry: route by operation
    workflow.set_entry_point("normalize_event")  # default, overridden by conditional

    # --- Remember pipeline ---
    workflow.add_edge("normalize_event", "embed_content")
    workflow.add_edge("embed_content", "store_memory")

    # --- Recall pipeline ---
    workflow.add_edge("embed_query", "vector_search")
    workflow.add_edge("vector_search", "format_results")

    # --- Consolidate pipeline ---
    workflow.add_edge("apply_decay", "find_and_merge")
    workflow.add_edge("find_and_merge", "prune_memories")
    workflow.add_edge("prune_memories", "extract_profile")

    # Send to appropriate END
    workflow.add_edge("store_memory", END)
    workflow.add_edge("format_results", END)
    workflow.add_edge("extract_profile", END)

    return workflow.compile()


# Module-level compiled graph
memory_graph = create_memory_graph()
