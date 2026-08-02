"""
NutriAgent Backend — Memory Agent Schemas.

Input: MemoryEvent — raw preference/feedback/conversation event to remember
Output: PreferenceProfile — extracted long-term user preferences
Infrastructure: MemoryEntry, MemorySearchResult, MemoryQuery
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Memory Types
# ============================================================================


class MemoryEvent(BaseModel):
    """
    A raw event to be encoded as a long-term memory.

    Events can come from various sources:
    - explicit_feedback: user said they like/dislike something
    - meal_record: a meal was logged
    - recommendation_feedback: user rated a recommendation
    - conversation: user mentioned a preference in chat
    - health_goal_change: user updated their health goals
    - implicit_behavior: system inferred a preference from behavior
    """

    user_id: UUID = Field(..., description="用户ID")
    source: Literal[
        "explicit_feedback",
        "meal_record",
        "recommendation_feedback",
        "conversation",
        "health_goal_change",
        "implicit_behavior",
        "manual",
    ] = Field(..., description="事件来源")
    source_id: UUID | None = Field(None, description="关联的源记录ID")
    event_type: Literal["like", "dislike", "prefer", "avoid", "crave", "tired_of", "goal", "habit", "context"] = Field(
        ..., description="事件类型"
    )

    # Content
    content: str = Field(..., min_length=1, max_length=2000, description="事件内容（自然语言描述）")
    title: str = Field("", max_length=256, description="事件概要（留空则自动生成）")

    # Target entity (optional)
    food_name: str | None = Field(None, description="关联的食物名称")
    food_id: UUID | None = Field(None, description="关联的食物ID")
    category: str | None = Field(None, description="关联的食物类别")

    # Signal strength
    confidence: float = Field(0.7, ge=0, le=1, description="置信度")
    importance: float = Field(0.5, ge=0, le=1, description="重要性")

    # Context
    context: dict = Field(default_factory=dict, description="触发上下文（时间、地点、场景等）")
    tags: list[str] = Field(default_factory=list, description="标签")


class MemoryEntry(BaseModel):
    """A stored memory record retrieved from the vector database."""

    id: UUID
    user_id: UUID
    memory_type: str  # fact | preference | episode | summary | goal
    title: str
    content: str
    key_facts: list = Field(default_factory=list)

    # Lifecycle
    importance: float = 0.5
    confidence: float = 1.0
    access_count: int = 0
    last_accessed_at: datetime | None = None
    decay_factor: float = 1.0

    # Provenance
    source: str = "manual"
    source_id: UUID | None = None

    # Similarity
    similarity_score: float | None = Field(None, description="向量相似度分数（仅搜索时返回）")

    # Timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}


# ============================================================================
# Query & Search
# ============================================================================


class MemoryQuery(BaseModel):
    """Query to search for relevant memories."""

    user_id: UUID = Field(..., description="用户ID")
    query_text: str = Field(..., min_length=1, max_length=1000, description="自然语言查询")
    memory_type: str | None = Field(None, description="过滤记忆类型")
    min_importance: float = Field(0.0, ge=0, le=1, description="最低重要性")
    min_confidence: float = Field(0.0, ge=0, le=1, description="最低置信度")
    top_k: int = Field(10, ge=1, le=50, description="返回结果数")
    include_expired: bool = Field(False, description="是否包含已过期记忆")
    context_filter: dict | None = Field(None, description="上下文过滤条件")


class MemorySearchResult(BaseModel):
    """Result of a memory search query."""

    query_text: str
    results: list[MemoryEntry] = Field(default_factory=list)
    total_found: int = 0
    search_type: str = "semantic"  # semantic | keyword | hybrid
    retrieved_at: datetime | None = None


# ============================================================================
# Preference Profile
# ============================================================================


class ExtractedPreference(BaseModel):
    """A single extracted preference from consolidated memories."""

    category: str = Field(..., description="偏好类别：food | cuisine | taste | cooking | timing | budget | scenario")
    key: str = Field(..., description="偏好键：如 'spice_level', '川菜', '三文鱼'")
    value: str = Field(..., description="偏好值：如 'high', 'like', 'avoid'")
    confidence: float = Field(..., ge=0, le=1)
    evidence_count: int = Field(0, description="支持此偏好的记忆数量")
    last_updated: datetime | None = None
    source_memory_ids: list[UUID] = Field(default_factory=list)


class PreferenceProfile(BaseModel):
    """
    Complete extracted user preference profile.

    Built by consolidating all preference-type memories
    and extracting structured preferences.
    """

    user_id: UUID
    generated_at: datetime | None = None

    # Taste preferences
    spice_level: float | None = Field(None, ge=0, le=5, description="辣度偏好 0-5")
    sweet_level: float | None = Field(None, ge=0, le=5)
    oil_level: float | None = Field(None, ge=0, le=5)

    # Food preferences
    liked_foods: list[ExtractedPreference] = Field(default_factory=list, description="喜欢的食物")
    disliked_foods: list[ExtractedPreference] = Field(default_factory=list, description="不喜欢的食物")
    craved_foods: list[ExtractedPreference] = Field(default_factory=list, description="渴望的食物")
    avoided_foods: list[ExtractedPreference] = Field(default_factory=list, description="主动避免的食物")

    # Cuisine preferences
    favorite_cuisines: list[ExtractedPreference] = Field(default_factory=list)
    avoided_cuisines: list[ExtractedPreference] = Field(default_factory=list)

    # Cooking & meal patterns
    cooking_preferences: list[ExtractedPreference] = Field(default_factory=list)
    meal_timing_patterns: list[ExtractedPreference] = Field(default_factory=list)
    budget_preference: ExtractedPreference | None = None

    # Health goals from memory
    health_goal_history: list[ExtractedPreference] = Field(default_factory=list)

    # Contextual preferences
    contextual_preferences: list[ExtractedPreference] = Field(
        default_factory=list,
        description="场景相关偏好：如 '加班时喜欢吃轻食'",
    )

    # Summary
    total_memories: int = 0
    total_preferences_extracted: int = 0
    profile_confidence: float = Field(0, ge=0, le=1, description="整体画像置信度")

    # Narrative summary
    narrative_summary: str = Field("", description="自然语言偏好概述")


# ============================================================================
# Memory Operations
# ============================================================================


class ConsolidateRequest(BaseModel):
    """Request to consolidate (merge & clean) memories for a user."""

    user_id: UUID
    similarity_threshold: float = Field(0.85, ge=0.5, le=1.0, description="合并的相似度阈值")
    max_memories: int = Field(1000, ge=100, le=10000, description="最大保留记忆数")
    min_importance: float = Field(0.05, ge=0, le=1, description="低于此重要性的记忆将被清理")


class ConsolidateResult(BaseModel):
    """Result of memory consolidation."""

    user_id: UUID
    memories_before: int = 0
    memories_after: int = 0
    merged_count: int = 0
    pruned_count: int = 0
    new_profile: PreferenceProfile | None = None
