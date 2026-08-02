"""
NutriAgent Backend — Food Log Domain Models.

Maps to: food_logs, food_log_items, daily_nutrition_summary
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, time

from sqlalchemy import (
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
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ============================================================================
# Enums
# ============================================================================


class MealTypeEnum(str, enum.Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"
    snack = "snack"
    late_night = "late_night"


class SourceTypeEnum(str, enum.Enum):
    manual = "manual"
    photo = "photo"
    voice = "voice"
    delivery_order = "delivery_order"
    ai_estimate = "ai_estimate"


# ============================================================================
# Models
# ============================================================================


class FoodLog(Base):
    __tablename__ = "food_logs"

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
    meal_type: Mapped[MealTypeEnum] = mapped_column(
        Enum(MealTypeEnum, name="meal_type_enum", create_type=False),
        nullable=False,
    )
    meal_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=text("CURRENT_DATE"))
    meal_time: Mapped[time] = mapped_column(Time, nullable=False, server_default=text("CURRENT_TIME"))
    source: Mapped[SourceTypeEnum] = mapped_column(
        Enum(SourceTypeEnum, name="source_type_enum", create_type=False),
        default=SourceTypeEnum.manual,
        server_default=text("'manual'"),
    )

    # Aggregated totals (maintained by DB trigger)
    total_kcal: Mapped[float] = mapped_column(Float(7), default=0, server_default=text("0"))
    total_protein_g: Mapped[float] = mapped_column(Float(6), default=0, server_default=text("0"))
    total_fat_g: Mapped[float] = mapped_column(Float(6), default=0, server_default=text("0"))
    total_carbs_g: Mapped[float] = mapped_column(Float(6), default=0, server_default=text("0"))
    total_fiber_g: Mapped[float] = mapped_column(Float(6), default=0, server_default=text("0"))
    total_sodium_mg: Mapped[float] = mapped_column(Float(7), default=0, server_default=text("0"))
    total_caffeine_mg: Mapped[float] = mapped_column(Float(6), default=0, server_default=text("0"))

    # User notes
    mood_before: Mapped[int | None] = mapped_column(SmallInteger, CheckConstraint("mood_before BETWEEN 1 AND 5"))
    mood_after: Mapped[int | None] = mapped_column(SmallInteger, CheckConstraint("mood_after BETWEEN 1 AND 5"))
    satiety_level: Mapped[int | None] = mapped_column(SmallInteger, CheckConstraint("satiety_level BETWEEN 1 AND 5"))
    notes: Mapped[str | None] = mapped_column(Text)
    photo_url: Mapped[str | None] = mapped_column(String(512))

    # Context
    location: Mapped[str | None] = mapped_column(String(256))
    eaten_with: Mapped[str | None] = mapped_column(String(256))
    cost_cent: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    # Relationships
    items: Mapped[list[FoodLogItem]] = relationship(
        "FoodLogItem", back_populates="food_log", lazy="selectin", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<FoodLog {self.id} — {self.meal_type.value} on {self.meal_date}>"


class FoodLogItem(Base):
    __tablename__ = "food_log_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    food_log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("food_logs.id", ondelete="CASCADE"),
        nullable=False,
    )
    food_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("foods.id")
    )

    # Food snapshot
    food_name: Mapped[str] = mapped_column(String(256), nullable=False)
    serving_size_g: Mapped[float] = mapped_column(
        Float(7), CheckConstraint("serving_size_g > 0"), nullable=False
    )
    serving_unit: Mapped[str] = mapped_column(String(32), default="g", server_default=text("'g'"))

    # Actual nutrition intake (per serving)
    energy_kcal: Mapped[float] = mapped_column(Float(7), nullable=False)
    protein_g: Mapped[float] = mapped_column(Float(6), default=0, server_default=text("0"))
    fat_g: Mapped[float] = mapped_column(Float(6), default=0, server_default=text("0"))
    carbs_g: Mapped[float] = mapped_column(Float(6), default=0, server_default=text("0"))
    fiber_g: Mapped[float] = mapped_column(Float(6), default=0, server_default=text("0"))
    sodium_mg: Mapped[float] = mapped_column(Float(7), default=0, server_default=text("0"))
    caffeine_mg: Mapped[float] = mapped_column(Float(6), default=0, server_default=text("0"))

    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    # Relationships
    food_log: Mapped[FoodLog] = relationship("FoodLog", back_populates="items")
    food: Mapped["Food | None"] = relationship("Food", lazy="selectin")

    def __repr__(self) -> str:
        return f"<FoodLogItem {self.food_name} {self.serving_size_g}g>"


class DailyNutritionSummary(Base):
    __tablename__ = "daily_nutrition_summary"

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
    summary_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Intake totals
    total_kcal: Mapped[float] = mapped_column(Float(7), default=0, server_default=text("0"))
    total_protein_g: Mapped[float] = mapped_column(Float(6), default=0, server_default=text("0"))
    total_fat_g: Mapped[float] = mapped_column(Float(6), default=0, server_default=text("0"))
    total_carbs_g: Mapped[float] = mapped_column(Float(6), default=0, server_default=text("0"))
    total_fiber_g: Mapped[float] = mapped_column(Float(6), default=0, server_default=text("0"))
    total_sodium_mg: Mapped[float] = mapped_column(Float(7), default=0, server_default=text("0"))
    total_caffeine_mg: Mapped[float] = mapped_column(Float(6), default=0, server_default=text("0"))

    # Goal vs actual
    kcal_target: Mapped[int | None] = mapped_column(Integer)
    kcal_achievement_pct: Mapped[float | None] = mapped_column(Float(5))
    meal_count: Mapped[int] = mapped_column(SmallInteger, default=0, server_default=text("0"))

    # AI scoring
    nutrition_score: Mapped[int | None] = mapped_column(
        SmallInteger, CheckConstraint("nutrition_score BETWEEN 0 AND 100")
    )
    score_feedback: Mapped[str | None] = mapped_column(Text)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (UniqueConstraint("user_id", "summary_date"),)

    def __repr__(self) -> str:
        return f"<DailyNutritionSummary {self.user_id} {self.summary_date}>"
