"""
NutriAgent Backend — Agent Memory Domain Models.

Maps to: agent_memories, agent_memory_links, agent_preference_signals
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ============================================================================
# Enums
# ============================================================================


class MemoryTypeEnum(str, enum.Enum):
    fact = "fact"
    preference = "preference"
    episode = "episode"
    summary = "summary"
    goal = "goal"


# ============================================================================
# Models
# ============================================================================


class AgentMemory(Base):
    __tablename__ = "agent_memories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    memory_type: Mapped[MemoryTypeEnum] = mapped_column(
        Enum(MemoryTypeEnum, name="memory_type_enum", create_type=False),
        nullable=False,
    )

    # Memory content
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    key_facts: Mapped[list] = mapped_column(JSON, default=list, server_default=text("'[]'"))

    # Weight & decay
    importance: Mapped[float] = mapped_column(
        Float(2),
        CheckConstraint("importance BETWEEN 0 AND 1"),
        default=0.5,
        server_default=text("0.5"),
    )
    access_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decay_factor: Mapped[float] = mapped_column(
        Float(3), default=1.0, server_default=text("1.0"),
    )

    # Provenance
    source: Mapped[str] = mapped_column(
        String(64), default="conversation", server_default=text("'conversation'")
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    confidence: Mapped[float] = mapped_column(
        Float(2),
        CheckConstraint("confidence BETWEEN 0 AND 1"),
        default=1.0,
        server_default=text("1.0"),
    )

    # pgvector embedding
    embedding: Mapped[str | None] = mapped_column(String(8192))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    source_links: Mapped[list[AgentMemoryLink]] = relationship(
        "AgentMemoryLink",
        foreign_keys="AgentMemoryLink.source_memory_id",
        back_populates="source_memory",
        lazy="selectin",
    )
    target_links: Mapped[list[AgentMemoryLink]] = relationship(
        "AgentMemoryLink",
        foreign_keys="AgentMemoryLink.target_memory_id",
        back_populates="target_memory",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<AgentMemory {self.memory_type.value}: {self.title}>"


class AgentMemoryLink(Base):
    __tablename__ = "agent_memory_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source_memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_memories.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_memories.id", ondelete="CASCADE"),
        nullable=False,
    )
    relation: Mapped[str] = mapped_column(String(128), nullable=False)
    weight: Mapped[float] = mapped_column(Float(2), default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("source_memory_id", "target_memory_id", "relation"),
    )

    source_memory: Mapped[AgentMemory] = relationship(
        "AgentMemory", foreign_keys=[source_memory_id], back_populates="source_links"
    )
    target_memory: Mapped[AgentMemory] = relationship(
        "AgentMemory", foreign_keys=[target_memory_id], back_populates="target_links"
    )


class AgentPreferenceSignal(Base):
    __tablename__ = "agent_preference_signals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    food_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("foods.id")
    )
    food_name: Mapped[str | None] = mapped_column(String(256))

    # Signal
    signal_type: Mapped[str] = mapped_column(String(32), nullable=False)
    signal_strength: Mapped[float] = mapped_column(
        Float(2),
        CheckConstraint("signal_strength BETWEEN 0 AND 1"),
        default=0.7,
        server_default=text("0.7"),
    )
    signal_source: Mapped[str | None] = mapped_column(String(64))
    context: Mapped[dict | None] = mapped_column(JSON)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))

    last_signal_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
