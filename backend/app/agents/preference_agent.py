"""
NutriAgent Backend — Preference Agent.

Extracts + classifies user nutrition preferences.
- Intent classification: "preference" vs "temporary craving"
- Conflict resolution: explicit > inferred, recent > old
- Decay: last_confirmed_at for stale preference pruning
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.database import get_session
from app.models.user_nutrition_preference import UserNutritionPreference
from sqlalchemy import select, text as sa_text


# Temporary craving keywords → IGNORE (don't save as preference)
TEMP_CRAVING_PATTERNS = ["想吃", "今天想", "现在想", "突然想", "馋"]
# True preference keywords → SAVE
PREFERENCE_PATTERNS = ["不吃", "不喜欢", "讨厌", "过敏", "不能吃", "喜欢吃", "爱吃", "喜欢", "最爱", "一直", "总是", "习惯"]


class PreferenceAgent:
    """Extracts and manages user nutrition preferences with intent classification."""

    # ── Intent classification ────────────────────

    @staticmethod
    def classify_intent(text: str) -> tuple[str, float]:
        """
        Classify text as 'preference' or 'craving'.

        Returns: (intent_type, confidence)
          - 'preference': should save to preferences (confidence 0.85)
          - 'craving': temporary, should IGNORE (confidence 0.3)
        """
        text_lower = text.lower()

        # Check temporary patterns first
        for pat in TEMP_CRAVING_PATTERNS:
            if pat in text_lower:
                return ("craving", 0.3)

        # Check preference patterns
        for pat in PREFERENCE_PATTERNS:
            if pat in text_lower:
                return ("preference", 0.85)

        # Default: weak preference
        return ("preference", 0.5)

    # ── Extract from chat text ────────────────────

    async def extract_from_chat(self, user_id: UUID, text: str) -> dict:
        """
        Extract preferences from chat text with intent classification.
        Returns {added, ignored, reason}.
        """
        intent, confidence = self.classify_intent(text)

        if intent == "craving":
            return {"added": 0, "ignored": 1, "reason": "temporary craving, not saved as preference"}

        added = 0
        async with get_session() as db:
            for kw in ["不吃", "不喜欢", "讨厌", "过敏", "不能吃"]:
                idx = text.find(kw)
                if idx >= 0:
                    after = text[idx + len(kw):].strip()
                    food = after[:6].strip()
                    if food and len(food) >= 1:
                        await self._upsert_pref(db, user_id, "food_dislike", food, "dislike", confidence, "chat_extract")
                        added += 1

            for kw in ["喜欢吃", "爱吃", "喜欢", "最爱"]:
                idx = text.find(kw)
                if idx >= 0:
                    after = text[idx + len(kw):].strip()
                    food = after[:6].strip()
                    if food and len(food) >= 1:
                        await self._upsert_pref(db, user_id, "food_like", food, "like", confidence, "chat_extract")
                        added += 1

        return {"added": added, "ignored": 0, "reason": f"{intent} intent, {added} extracted"}

    # ── Infer from food logs ──────────────────────

    async def infer_from_food_logs(self, user_id: UUID, days: int = 30) -> int:
        """Infer preferences from frequent foods in recent logs."""
        added = 0
        async with get_session() as db:
            r = await db.execute(sa_text(
                """SELECT food_name, count(*) as cnt FROM food_log_items
                   WHERE food_log_id IN (SELECT id FROM food_logs WHERE user_id=:uid)
                   GROUP BY food_name ORDER BY cnt DESC LIMIT 10""",
            ), {"uid": user_id})
            for row in r.fetchall():
                if row.cnt >= 3:
                    # Inferred preferences get lower confidence + don't override manual
                    await self._upsert_pref(db, user_id, "food_like", row.food_name, "frequent",
                                            min(0.9, 0.5 + row.cnt * 0.05), "food_log_infer",
                                            respect_existing=True)
                    added += 1
        return added

    # ── Get preferences (with decay) ──────────────

    async def get_preferences(self, user_id: UUID) -> dict:
        """Get active preferences grouped by type. Stale preferences (>90 days unconfirmed) excluded."""
        async with get_session() as db:
            r = await db.execute(
                select(UserNutritionPreference)
                .where(UserNutritionPreference.user_id == user_id)
                .order_by(UserNutritionPreference.confidence.desc())
            )
            prefs = r.scalars().all()

        result = {"food_like": [], "food_dislike": [], "budget": [], "cuisine": [], "cooking": [], "timing": []}
        now = datetime.now(timezone.utc)
        for p in prefs:
            # Stale check: >90 days unconfirmed → skip
            if p.last_confirmed_at is None and p.source == "food_log_infer":
                age = (now - p.created_at.replace(tzinfo=timezone.utc)).days
                if age > 90:
                    continue
            bucket = result.get(p.preference_type, [])
            bucket.append({"key": p.preference_key, "value": p.preference_value, "confidence": p.confidence, "source": p.source})

        return result

    # ── Conflict resolver ─────────────────────────

    async def _upsert_pref(self, db, user_id, ptype, key, value, confidence, source, respect_existing=False):
        """Upsert with conflict resolution: explicit > inferred."""
        existing = await db.execute(
            select(UserNutritionPreference).where(
                UserNutritionPreference.user_id == user_id,
                UserNutritionPreference.preference_type == ptype,
                UserNutritionPreference.preference_key == key,
            )
        )
        pref = existing.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if pref:
            # Conflict resolution:
            #   chat_extract > manual > food_log_infer
            source_rank = {"chat_extract": 3, "manual": 2, "food_log_infer": 1}

            if source_rank.get(source, 0) >= source_rank.get(pref.source, 0):
                # Only overwrite if same or higher authority
                pref.preference_value = value
                pref.confidence = max(pref.confidence, confidence)
                pref.last_confirmed_at = now

            # Even if we don't overwrite, bump last_confirmed for active prefs
            if source_rank.get(source, 0) >= 2:
                pref.last_confirmed_at = now
            pref.updated_at = now
        else:
            if respect_existing:
                return  # Don't create new from inference if explicit exists
            db.add(UserNutritionPreference(
                user_id=user_id, preference_type=ptype, preference_key=key,
                preference_value=value, confidence=confidence, source=source,
                last_confirmed_at=now,
            ))
        await db.flush()


# Singleton
preference_agent = PreferenceAgent()
