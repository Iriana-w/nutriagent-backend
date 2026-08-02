"""
NutriAgent Backend — Context Assembly Node.

Gathers all contextual information needed for personalized recommendations:
- User profile & health data
- Time of day / season / weather context
- Recent nutrition history & gaps
"""

from __future__ import annotations

from datetime import datetime

from app.agents.state import RecommendationState
from app.tools.user_context import UserContext


class ContextAssembler:
    """Assembles rich context for the recommendation engine."""

    async def assemble(self, state: RecommendationState) -> RecommendationState:
        """Gather user context and enrich state."""

        # --- User Context ---
        ctx = UserContext(state.user_id)
        try:
            state.user_context = await ctx.assemble()
        except Exception:
            state.user_context = {"error": "Failed to load user context"}

        # --- Time Context ---
        state.time_context = self._build_time_context()

        # --- Nutrition Gaps ---
        gaps = state.user_context.get("nutrition_gaps", {})
        state.nutrition_gaps = gaps.get("suggested_focus", [])

        return state

    @staticmethod
    def _build_time_context() -> dict:
        """Build time-of-day, day-of-week, and seasonal context."""
        now = datetime.now()
        hour = now.hour
        month = now.month
        weekday = now.weekday()  # 0=Monday

        # Meal timing
        if 6 <= hour < 10:
            current_meal = "breakfast"
            meal_time_desc = "早餐时间"
        elif 10 <= hour < 14:
            current_meal = "lunch"
            meal_time_desc = "午餐时间"
        elif 14 <= hour < 18:
            current_meal = "snack"
            meal_time_desc = "下午茶/加餐时间"
        elif 18 <= hour < 21:
            current_meal = "dinner"
            meal_time_desc = "晚餐时间"
        else:
            current_meal = "late_night"
            meal_time_desc = "深夜时段"

        # Season (Northern Hemisphere)
        if 3 <= month <= 5:
            season = "春季"
            seasonal_tip = "春季宜养肝，多吃绿色蔬菜，少酸多甘"
        elif 6 <= month <= 8:
            season = "夏季"
            seasonal_tip = "夏季宜清热解暑，多喝水，适量补充电解质"
        elif 9 <= month <= 11:
            season = "秋季"
            seasonal_tip = "秋季宜润燥养肺，多吃白色食物（梨、银耳、山药）"
        else:
            season = "冬季"
            seasonal_tip = "冬季宜温补，多食根茎类蔬菜和温热食物"

        # Workday context for programmers
        is_weekend = weekday >= 5
        work_context = (
            "周末——可能有更多时间准备食物或外出就餐"
            if is_weekend
            else "工作日——可能需要快速便捷的饮食方案"
        )

        return {
            "current_time": now.strftime("%H:%M"),
            "current_meal": current_meal,
            "meal_time_desc": meal_time_desc,
            "day_of_week": weekday,
            "is_weekend": is_weekend,
            "season": season,
            "seasonal_tip": seasonal_tip,
            "work_context": work_context,
            "month": month,
        }
