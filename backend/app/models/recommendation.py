"""
NutriAgent Backend — Recommendation Domain Models.

Maps to: recommendation_logs, recommendation_items, meal_plans, meal_plan_items
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ============================================================================
# Enums
# ============================================================================


class FeedbackEnum(str, enum.Enum):
    positive = "positive"
    negative = "negative"
    neutral = "neutral"
    skip = "skip"


class RecommendStatusEnum(str, enum.Enum):
    generated = "generated"
    presented = "presented"
    accepted = "accepted"
    rejected = "rejected"
    expired = "expired"


# ============================================================================
# Models
# ============================================================================


class RecommendationLog(Base):
    __tablename__ = "recommendation_logs"

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

    # Metadata
    recommend_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scenario: Mapped[str | None] = mapped_column(String(64))
    meal_type: Mapped[str | None] = mapped_column(String(32))  # meal_type_enum
    target_date: Mapped[date | None] = mapped_column(Date)

    # AI generation info
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(32))
    prompt_template_id: Mapped[str | None] = mapped_column(String(64))
    retrieval_sources: Mapped[dict | None] = mapped_column(JSON)

    # Generated content
    recommendation_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Token tracking
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)

    # Status & feedback
    status: Mapped[RecommendStatusEnum] = mapped_column(
        Enum(RecommendStatusEnum, name="recommend_status_enum", create_type=False),
        default=RecommendStatusEnum.generated,
        server_default=text("'generated'"),
    )
    presented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    feedback: Mapped[FeedbackEnum | None] = mapped_column(
        Enum(FeedbackEnum, name="feedback_enum", create_type=False),
    )
    feedback_detail: Mapped[str | None] = mapped_column(Text)
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    # Relationships
    items: Mapped[list[RecommendationItem]] = relationship(
        "RecommendationItem",
        back_populates="recommendation",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<RecommendationLog {self.id} — {self.recommend_type}>"


class RecommendationItem(Base):
    __tablename__ = "recommendation_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recommendation_logs.id", ondelete="CASCADE"),
        nullable=False,
    )

    item_type: Mapped[str] = mapped_column(String(32), default="food", server_default=text("'food'"))
    food_name: Mapped[str] = mapped_column(String(256), nullable=False)
    food_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("foods.id")
    )
    delivery_dish_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("delivery_dishes.id")
    )

    serving_size_g: Mapped[float | None] = mapped_column(Float(7))
    estimated_kcal: Mapped[float | None] = mapped_column(Float(7))
    estimated_protein_g: Mapped[float | None] = mapped_column(Float(6))
    estimated_fat_g: Mapped[float | None] = mapped_column(Float(6))
    estimated_carbs_g: Mapped[float | None] = mapped_column(Float(6))

    # Explainability
    reason_text: Mapped[str | None] = mapped_column(Text)
    nutrition_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), server_default=text("'{}'"))

    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)

    # Per-item feedback
    item_feedback: Mapped[FeedbackEnum | None] = mapped_column(
        Enum(FeedbackEnum, name="feedback_enum", create_type=False),
    )
    was_consumed: Mapped[bool | None] = mapped_column(Boolean)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    # Relationships
    recommendation: Mapped[RecommendationLog] = relationship(
        "RecommendationLog", back_populates="items"
    )


class MealPlan(Base):
    __tablename__ = "meal_plans"

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
    plan_week_start: Mapped[date] = mapped_column(Date, nullable=False)
    plan_name: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), default="active", server_default=text("'active'"))

    # Target nutrition
    daily_kcal_target: Mapped[int | None] = mapped_column(Integer)
    daily_protein_g: Mapped[float | None] = mapped_column(Float(6))
    daily_fat_g: Mapped[float | None] = mapped_column(Float(6))
    daily_carbs_g: Mapped[float | None] = mapped_column(Float(6))

    # Source
    source_recommendation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recommendation_logs.id")
    )

    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (UniqueConstraint("user_id", "plan_week_start"),)

    # Relationships
    items: Mapped[list[MealPlanItem]] = relationship(
        "MealPlanItem",
        back_populates="meal_plan",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class MealPlanItem(Base):
    __tablename__ = "meal_plan_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    meal_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meal_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    meal_type: Mapped[str] = mapped_column(String(32), nullable=False)

    food_name: Mapped[str] = mapped_column(String(256), nullable=False)
    food_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("foods.id")
    )
    serving_size_g: Mapped[float | None] = mapped_column(Float(7))
    estimated_kcal: Mapped[float | None] = mapped_column(Float(7))

    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    actual_food_log_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("food_logs.id")
    )

    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    # Relationships
    meal_plan: Mapped[MealPlan] = relationship("MealPlan", back_populates="items")
