"""
NutriAgent Backend — User Domain Models.

Maps to: users, user_health_profiles, user_diet_types, user_health_goals,
         user_allergens, user_preferences, user_caffeine_logs
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
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
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base  # Will be defined in models/__init__.py

# ============================================================================
# Python Enums (mirroring PostgreSQL enum types from schema.sql)
# ============================================================================


class GenderEnum(str, enum.Enum):
    male = "male"
    female = "female"
    other = "other"
    prefer_not_to_say = "prefer_not_to_say"


class ActivityLevelEnum(str, enum.Enum):
    sedentary = "sedentary"
    light = "light"
    moderate = "moderate"
    active = "active"
    very_active = "very_active"


class DietTypeEnum(str, enum.Enum):
    omnivore = "omnivore"
    vegetarian = "vegetarian"
    vegan = "vegan"
    keto = "keto"
    low_carb = "low_carb"
    paleo = "paleo"
    mediterranean = "mediterranean"
    dash = "dash"
    gluten_free = "gluten_free"
    halal = "halal"
    custom = "custom"


class GoalTypeEnum(str, enum.Enum):
    lose_weight = "lose_weight"
    gain_muscle = "gain_muscle"
    maintain = "maintain"
    blood_sugar = "blood_sugar"
    eye_health = "eye_health"
    hair_health = "hair_health"
    gut_health = "gut_health"
    energy_boost = "energy_boost"
    anti_inflammatory = "anti_inflammatory"
    heart_health = "heart_health"


class SeverityEnum(str, enum.Enum):
    mild = "mild"
    moderate = "moderate"
    severe = "severe"


# ============================================================================
# Models
# ============================================================================


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    wechat_union_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    wechat_open_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    nickname: Mapped[str] = mapped_column(String(64))
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    gender: Mapped[GenderEnum | None] = mapped_column(
        Enum(GenderEnum, name="gender_enum", create_type=False)
    )

    # Auth
    password_hash: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_ip: Mapped[str | None] = mapped_column(INET)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    health_profile: Mapped[UserHealthProfile | None] = relationship(
        "UserHealthProfile",
        back_populates="user",
        uselist=False,
        lazy="selectin",
    )
    diet_types: Mapped[list[UserDietType]] = relationship(
        "UserDietType", back_populates="user", lazy="selectin"
    )
    health_goals: Mapped[list[UserHealthGoal]] = relationship(
        "UserHealthGoal", back_populates="user", lazy="selectin"
    )
    allergens: Mapped[list[UserAllergen]] = relationship(
        "UserAllergen", back_populates="user", lazy="selectin"
    )
    preferences: Mapped[UserPreferences | None] = relationship(
        "UserPreferences", back_populates="user", uselist=False, lazy="selectin"
    )
    caffeine_logs: Mapped[list[UserCaffeineLog]] = relationship(
        "UserCaffeineLog", back_populates="user", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User {self.id} — {self.nickname}>"


class UserHealthProfile(Base):
    __tablename__ = "user_health_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # Body metrics
    gender: Mapped[GenderEnum | None] = mapped_column(
        Enum(GenderEnum, name="gender_enum", create_type=False)
    )
    birth_date: Mapped[date | None] = mapped_column(Date)
    height_cm: Mapped[float | None] = mapped_column(
        Float(5), CheckConstraint("height_cm BETWEEN 50 AND 300")
    )
    weight_kg: Mapped[float | None] = mapped_column(
        Float(5), CheckConstraint("weight_kg BETWEEN 20 AND 500")
    )
    # BMI is GENERATED ALWAYS AS STORED — read-only
    bmi: Mapped[float | None] = mapped_column(Float(4), server_default=FetchedValue())
    body_fat_pct: Mapped[float | None] = mapped_column(
        Float(4), CheckConstraint("body_fat_pct BETWEEN 1 AND 70")
    )
    muscle_mass_kg: Mapped[float | None] = mapped_column(Float(5))
    waist_cm: Mapped[float | None] = mapped_column(Float(5))
    # BMR is computed by DB trigger — read-only in Python
    bmr_kcal: Mapped[int | None] = mapped_column(Integer)
    daily_kcal_target: Mapped[int | None] = mapped_column(
        Integer, CheckConstraint("daily_kcal_target BETWEEN 800 AND 6000")
    )

    # Macro targets (%)
    target_protein_pct: Mapped[float] = mapped_column(
        Float(4), default=20, server_default=text("20")
    )
    target_fat_pct: Mapped[float] = mapped_column(
        Float(4), default=30, server_default=text("30")
    )
    target_carbs_pct: Mapped[float] = mapped_column(
        Float(4), default=50, server_default=text("50")
    )

    # Location
    city: Mapped[str | None] = mapped_column(String(64))
    district: Mapped[str | None] = mapped_column(String(64))
    province: Mapped[str | None] = mapped_column(String(64))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location_source: Mapped[str | None] = mapped_column(String(32), default="gps")

    # Activity
    activity_level: Mapped[ActivityLevelEnum] = mapped_column(
        Enum(ActivityLevelEnum, name="activity_level_enum", create_type=False),
        default=ActivityLevelEnum.sedentary,
        server_default=text("'sedentary'"),
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    # Relationship
    user: Mapped[User] = relationship("User", back_populates="health_profile")


class UserDietType(Base):
    __tablename__ = "user_diet_types"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    diet_type: Mapped[DietTypeEnum] = mapped_column(
        Enum(DietTypeEnum, name="diet_type_enum", create_type=False),
        primary_key=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    user: Mapped[User] = relationship("User", back_populates="diet_types")


class UserHealthGoal(Base):
    __tablename__ = "user_health_goals"

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
    goal_type: Mapped[GoalTypeEnum] = mapped_column(
        Enum(GoalTypeEnum, name="goal_type_enum", create_type=False),
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default=text("0")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    target_description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (UniqueConstraint("user_id", "goal_type"),)

    user: Mapped[User] = relationship("User", back_populates="health_goals")


class UserAllergen(Base):
    __tablename__ = "user_allergens"

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
    allergen: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[SeverityEnum] = mapped_column(
        Enum(SeverityEnum, name="severity_enum", create_type=False),
        default=SeverityEnum.moderate,
        server_default=text("'moderate'"),
    )
    notes: Mapped[str | None] = mapped_column(Text)
    verified_by_doctor: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (UniqueConstraint("user_id", "allergen"),)

    user: Mapped[User] = relationship("User", back_populates="allergens")


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Structured fields
    spice_level: Mapped[int | None] = mapped_column(SmallInteger, CheckConstraint("spice_level BETWEEN 0 AND 5"))
    sweet_level: Mapped[int | None] = mapped_column(SmallInteger, CheckConstraint("sweet_level BETWEEN 0 AND 5"))
    oil_level: Mapped[int | None] = mapped_column(SmallInteger, CheckConstraint("oil_level BETWEEN 0 AND 5"))
    budget_per_meal: Mapped[int | None] = mapped_column(Integer, CheckConstraint("budget_per_meal > 0"))

    # JSONB fields
    cuisine_prefs: Mapped[dict] = mapped_column(JSON, default=dict, server_default=text("'{}'"))
    food_blacklist: Mapped[list] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    food_whitelist: Mapped[list] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    cooking_prefs: Mapped[dict] = mapped_column(JSON, default=dict, server_default=text("'{}'"))
    meal_schedule: Mapped[dict] = mapped_column(JSON, default=dict, server_default=text("'{}'"))
    extra: Mapped[dict] = mapped_column(JSON, default=dict, server_default=text("'{}'"))

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    user: Mapped[User] = relationship("User", back_populates="preferences")


class UserCaffeineLog(Base):
    __tablename__ = "user_caffeine_logs"

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
    log_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=text("CURRENT_DATE"))
    total_mg: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    drink_count: Mapped[int] = mapped_column(SmallInteger, default=0, server_default=text("0"))
    target_limit_mg: Mapped[int] = mapped_column(Integer, default=400, server_default=text("400"))
    # over_limit is GENERATED ALWAYS AS STORED
    over_limit: Mapped[bool | None] = mapped_column(Boolean, server_default=FetchedValue())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (UniqueConstraint("user_id", "log_date"),)

    user: Mapped[User] = relationship("User", back_populates="caffeine_logs")
