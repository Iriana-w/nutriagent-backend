"""
NutriAgent Backend — User Context Tool.

Assembles comprehensive user context for the AI recommendation engine.
Includes user profile, health data, preferences, recent diet history, and
nutrition gap analysis.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.user import User, UserHealthProfile, UserPreferences
from app.models.food_log import FoodLog


class UserContext:
    """Assembles full user context for AI recommendation generation."""

    def __init__(self, user_id: str):
        self.user_id = UUID(user_id)

    async def assemble(self) -> dict:
        """Gather all relevant user context needed for recommendations."""
        async with get_session() as db:
            user = await db.get(User, self.user_id)
            if not user:
                return self._fallback_context()

            profile = await db.execute(
                select(UserHealthProfile).where(UserHealthProfile.user_id == self.user_id)
            )
            profile = profile.scalar_one_or_none()

            prefs = await db.execute(
                select(UserPreferences).where(UserPreferences.user_id == self.user_id)
            )
            prefs = prefs.scalar_one_or_none()

            # Recent 7-day food history
            seven_days_ago = date.today() - timedelta(days=7)
            recent_logs_stmt = (
                select(FoodLog)
                .where(
                    and_(
                        FoodLog.user_id == self.user_id,
                        FoodLog.meal_date >= seven_days_ago,
                    )
                )
                .order_by(FoodLog.meal_date.desc())
                .limit(30)
            )
            logs_result = await db.execute(recent_logs_stmt)
            recent_logs = logs_result.scalars().all()

            return {
                "user_id": str(user.id),
                "nickname": user.nickname,
                "gender": user.gender.value if user.gender else None,

                # Health profile
                "age": self._calc_age(profile.birth_date) if profile and profile.birth_date else None,
                "height_cm": float(profile.height_cm) if profile and profile.height_cm else None,
                "weight_kg": float(profile.weight_kg) if profile and profile.weight_kg else None,
                "bmi": float(profile.bmi) if profile and profile.bmi else None,
                "bmr_kcal": profile.bmr_kcal if profile else None,
                "daily_kcal_target": profile.daily_kcal_target if profile else 2000,
                "target_protein_pct": float(profile.target_protein_pct) if profile else 20,
                "target_fat_pct": float(profile.target_fat_pct) if profile else 30,
                "target_carbs_pct": float(profile.target_carbs_pct) if profile else 50,
                "activity_level": profile.activity_level.value if profile and profile.activity_level else "sedentary",

                # Diet types
                "diet_types": [dt.diet_type.value for dt in (user.diet_types or [])],

                # Health goals
                "health_goals": [
                    {
                        "goal": g.goal_type.value,
                        "priority": g.priority,
                        "description": g.target_description,
                    }
                    for g in (user.health_goals or [])
                    if g.is_active
                ],

                # Allergens
                "allergens": [
                    {"allergen": a.allergen, "severity": a.severity.value}
                    for a in (user.allergens or [])
                ],

                # Preferences
                "spice_level": prefs.spice_level if prefs else None,
                "sweet_level": prefs.sweet_level if prefs else None,
                "oil_level": prefs.oil_level if prefs else None,
                "budget_per_meal": prefs.budget_per_meal if prefs else None,
                "cuisine_prefs": prefs.cuisine_prefs if prefs else {},
                "food_blacklist": prefs.food_blacklist if prefs else [],
                "food_whitelist": prefs.food_whitelist if prefs else [],
                "cooking_prefs": prefs.cooking_prefs if prefs else {},
                "meal_schedule": prefs.meal_schedule if prefs else {},

                # Recent diet history summary
                "recent_meals": [
                    {
                        "date": str(log.meal_date),
                        "meal_type": log.meal_type.value,
                        "total_kcal": float(log.total_kcal) if log.total_kcal else 0,
                        "foods": [item.food_name for item in (log.items or [])],
                    }
                    for log in recent_logs[:21]  # ~7 days × 3 meals
                ],

                # Computed: nutrition gaps
                "nutrition_gaps": self._compute_gaps(recent_logs, profile),
            }

    def _fallback_context(self) -> dict:
        """Default context for new users (cold start)."""
        return {
            "user_id": str(self.user_id),
            "daily_kcal_target": 2000,
            "activity_level": "sedentary",
            "diet_types": ["omnivore"],
            "health_goals": [],
            "allergens": [],
            "recent_meals": [],
            "nutrition_gaps": {
                "message": "新用户，暂无足够数据进行营养缺口分析。基于中国居民膳食指南默认推荐。",
                "suggested_focus": ["均衡饮食", "增加蔬菜摄入", "适量蛋白质"],
            },
        }

    @staticmethod
    def _calc_age(birth_date: date) -> int | None:
        """Calculate age from birth date."""
        if not birth_date:
            return None
        today = date.today()
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

    @staticmethod
    def _compute_gaps(logs: list[FoodLog], profile: UserHealthProfile | None) -> dict:
        """Identify nutrition gaps from recent diet history."""
        if not logs or not profile:
            return {"message": "数据不足", "suggested_focus": []}

        # Average daily intake over logged days
        unique_days = {log.meal_date for log in logs}
        if not unique_days:
            return {"message": "暂无饮食记录", "suggested_focus": []}

        num_days = len(unique_days)
        total_kcal = sum(float(log.total_kcal or 0) for log in logs)
        avg_kcal = total_kcal / num_days if num_days > 0 else 0

        target = profile.daily_kcal_target or 2000
        gap_pct = round((target - avg_kcal) / target * 100, 0) if target > 0 else 0

        suggestions = []
        if gap_pct > 20:
            suggestions.append(f"热量摄入偏低（{gap_pct:.0f}%），建议增加营养密度高的食物")
        elif gap_pct < -20:
            suggestions.append(f"热量摄入偏高，建议控制份量并选择低热量高饱腹食物")

        return {
            "avg_daily_kcal": round(avg_kcal, 0),
            "kcal_target": target,
            "gap_pct": gap_pct,
            "num_days_tracked": num_days,
            "suggested_focus": suggestions or ["保持当前的饮食节奏"],
        }
