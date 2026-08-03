"""
User Nutrition Preference model — dynamic key-value preferences.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserNutritionPreference(Base):
    __tablename__ = "user_nutrition_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    preference_type: Mapped[str] = mapped_column(String(32), nullable=False)
    preference_key: Mapped[str] = mapped_column(String(128), nullable=False)
    preference_value: Mapped[str | None] = mapped_column(String(256))
    confidence: Mapped[float] = mapped_column(Float(2), default=1.0, server_default=text("1.0"))
    source: Mapped[str] = mapped_column(String(64), default="manual")
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    __table_args__ = (UniqueConstraint("user_id", "preference_type", "preference_key"),)
