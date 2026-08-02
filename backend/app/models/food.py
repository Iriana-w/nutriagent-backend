"""
NutriAgent Backend — Food & Delivery Domain Models.

Maps to: food_categories, foods, food_goal_tags, delivery_dishes
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    FetchedValue,
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


class FoodCategoryEnum(str, enum.Enum):
    staple = "staple"
    meat = "meat"
    poultry = "poultry"
    seafood = "seafood"
    egg = "egg"
    dairy = "dairy"
    legume = "legume"
    vegetable = "vegetable"
    fruit = "fruit"
    nut = "nut"
    oil = "oil"
    beverage = "beverage"
    snack = "snack"
    condiment = "condiment"
    supplement = "supplement"
    mixed_dish = "mixed_dish"
    fast_food = "fast_food"
    other = "other"


# ============================================================================
# Models
# ============================================================================


class FoodCategory(Base):
    __tablename__ = "food_categories"

    id: Mapped[int] = mapped_column(
        SmallInteger,
        primary_key=True,
        autoincrement=True,
    )
    category: Mapped[FoodCategoryEnum] = mapped_column(
        Enum(FoodCategoryEnum, name="food_category_enum", create_type=False),
        unique=True,
        nullable=False,
    )
    parent_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("food_categories.id")
    )
    name_zh: Mapped[str] = mapped_column(String(64), nullable=False)
    icon_emoji: Mapped[str | None] = mapped_column(String(8))
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)

    # Self-referential
    parent: Mapped[FoodCategory | None] = relationship(
        "FoodCategory", remote_side="FoodCategory.id", lazy="selectin"
    )
    children: Mapped[list[FoodCategory]] = relationship("FoodCategory", lazy="selectin")


class Food(Base):
    __tablename__ = "foods"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    category_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("food_categories.id"), nullable=False
    )

    # Basic info
    name_zh: Mapped[str] = mapped_column(String(128), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(128))
    alias: Mapped[list[str] | None] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    thumb_url: Mapped[str | None] = mapped_column(String(512))

    # Per 100g nutrition (main)
    energy_kcal: Mapped[float] = mapped_column(
        Float(7), CheckConstraint("energy_kcal >= 0"), nullable=False
    )
    energy_kj: Mapped[float | None] = mapped_column(Float(7), server_default=FetchedValue())  # GENERATED
    protein_g: Mapped[float] = mapped_column(
        Float(6), CheckConstraint("protein_g >= 0"), default=0, server_default=text("0")
    )
    fat_g: Mapped[float] = mapped_column(
        Float(6), CheckConstraint("fat_g >= 0"), default=0, server_default=text("0")
    )
    carbs_g: Mapped[float] = mapped_column(
        Float(6), CheckConstraint("carbs_g >= 0"), default=0, server_default=text("0")
    )
    fiber_g: Mapped[float] = mapped_column(
        Float(6), CheckConstraint("fiber_g >= 0"), default=0, server_default=text("0")
    )
    sugar_g: Mapped[float] = mapped_column(
        Float(6), CheckConstraint("sugar_g >= 0"), default=0, server_default=text("0")
    )
    sodium_mg: Mapped[float] = mapped_column(
        Float(7), CheckConstraint("sodium_mg >= 0"), default=0, server_default=text("0")
    )
    cholesterol_mg: Mapped[float] = mapped_column(
        Float(6), CheckConstraint("cholesterol_mg >= 0"), default=0, server_default=text("0")
    )

    # Micronutrients (programmer health focus)
    vitamin_a_ug: Mapped[float | None] = mapped_column(Float(7))
    vitamin_c_mg: Mapped[float | None] = mapped_column(Float(6))
    vitamin_e_mg: Mapped[float | None] = mapped_column(Float(6))
    lutein_ug: Mapped[float | None] = mapped_column(Float(7))  # Eye health
    omega3_g: Mapped[float | None] = mapped_column(Float(6))    # Anti-inflammatory
    caffeine_mg: Mapped[float | None] = mapped_column(Float(6))
    calcium_mg: Mapped[float | None] = mapped_column(Float(7))
    iron_mg: Mapped[float | None] = mapped_column(Float(6))
    zinc_mg: Mapped[float | None] = mapped_column(Float(6))
    magnesium_mg: Mapped[float | None] = mapped_column(Float(7))

    # Extra properties
    glycemic_index: Mapped[int | None] = mapped_column(
        SmallInteger, CheckConstraint("glycemic_index BETWEEN 0 AND 150")
    )
    edible_portion_pct: Mapped[float] = mapped_column(
        Float(4), default=100, server_default=text("100")
    )
    is_common: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    data_source: Mapped[str] = mapped_column(
        String(128), default="中国食物成分表", server_default=text("'中国食物成分表'")
    )

    # pgvector embedding (read-only for ORM; populated via raw SQL)
    # Mapped as a raw column — actual pgvector operations use text() SQL
    embedding: Mapped[str | None] = mapped_column(String(8192))  # Placeholder for VECTOR(1536)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    # Relationships
    category: Mapped[FoodCategory] = relationship("FoodCategory", lazy="selectin")
    goal_tags: Mapped[list[FoodGoalTag]] = relationship(
        "FoodGoalTag", back_populates="food", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Food {self.name_zh} ({self.energy_kcal}kcal/100g)>"


class FoodGoalTag(Base):
    __tablename__ = "food_goal_tags"

    food_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foods.id", ondelete="CASCADE"),
        primary_key=True,
    )
    goal_type: Mapped[str] = mapped_column(
        Enum(
            "lose_weight", "gain_muscle", "maintain", "blood_sugar",
            "eye_health", "hair_health", "gut_health", "energy_boost",
            "anti_inflammatory", "heart_health",
            name="goal_type_enum", create_type=False,
        ),
        primary_key=True,
    )
    relevance: Mapped[float] = mapped_column(
        Float(2), default=1.0, server_default=text("1.0")
    )

    food: Mapped[Food] = relationship("Food", back_populates="goal_tags")


class DeliveryDish(Base):
    __tablename__ = "delivery_dishes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    platform_dish_id: Mapped[str] = mapped_column(String(128), nullable=False)
    merchant_name: Mapped[str] = mapped_column(String(256), nullable=False)
    dish_name: Mapped[str] = mapped_column(String(256), nullable=False)
    price_cent: Mapped[int] = mapped_column(Integer, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(512))
    merchant_address: Mapped[str | None] = mapped_column(String(512))
    merchant_lat: Mapped[float | None] = mapped_column(Float(7))
    merchant_lng: Mapped[float | None] = mapped_column(Float(7))

    # AI-estimated nutrition
    estimated_kcal: Mapped[int | None] = mapped_column(Integer)
    estimated_protein_g: Mapped[float | None] = mapped_column(Float(5))
    estimated_fat_g: Mapped[float | None] = mapped_column(Float(5))
    estimated_carbs_g: Mapped[float | None] = mapped_column(Float(5))
    health_score: Mapped[int | None] = mapped_column(
        SmallInteger, CheckConstraint("health_score BETWEEN 0 AND 100")
    )

    raw_data: Mapped[dict | None] = mapped_column(JSON)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (UniqueConstraint("platform", "platform_dish_id"),)
