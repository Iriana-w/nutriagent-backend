"""
NutriAgent Backend — History Analyzer Tool.

Analyzes user diet history for the Recommendation Agent:
- Pattern detection (common foods, skipped meals, repeat frequency)
- Nutrition gap identification
- Like/dislike extraction from feedback
- Repeat avoidance list generation
"""

from __future__ import annotations

from datetime import date, timedelta

from app.schemas.recommendation_agent import (
    HealthGoalInput,
    HistorySummary,
    RecentMealItem,
)


class HistoryAnalyzer:
    """
    Analyzes user diet history for the recommendation engine.

    Extracts:
    - Foods to avoid (recent repeats, disliked)
    - Nutrition gaps from history
    - Eating patterns (skipped meals, timing preferences)
    - Preference signals (liked foods)
    """

    # Meal-type specific kcal targets (as % of daily target)
    MEAL_KCAL_PCT = {
        "breakfast": 0.28,
        "lunch": 0.38,
        "dinner": 0.28,
        "snack": 0.10,
        "late_night": 0.08,
    }

    def analyze(
        self,
        history: HistorySummary | None,
        health_goals: list[HealthGoalInput],
        meal_type: str,
        daily_kcal_target: int,
    ) -> dict:
        """
        Analyze history and return structured insights.

        Returns:
            dict with: avoided_foods, liked_foods, pattern_insights, gaps,
                       history_context_prompt, meal_kcal_target
        """
        result = {
            "avoided_foods": [],
            "liked_foods": [],
            "pattern_insights": [],
            "gaps": [],
            "history_context_prompt": "",
            "meal_kcal_target": self._meal_kcal_target(meal_type, daily_kcal_target),
        }

        if not history:
            result["history_context_prompt"] = "新用户，暂无饮食历史数据。基于默认推荐。"
            return result

        # --- 1. Collect avoided foods ---
        avoided = set()

        # Recent foods (last 3 days) — avoid repeats
        today = date.today()
        three_days_ago = today - timedelta(days=3)
        for meal in history.recent_meals:
            if meal.meal_date >= three_days_ago:
                avoided.add(meal.food_name)
        result["avoided_foods"] = list(avoided)

        # Disliked foods
        if history.disliked_foods:
            avoided.update(f.lower() for f in history.disliked_foods)
            result["avoided_foods"] = list(avoided)

        # --- 2. Liked foods ---
        if history.liked_foods:
            result["liked_foods"] = list(set(history.liked_foods))

        # --- 3. Pattern insights ---
        patterns = []

        # Skipped meals
        if history.skipped_meals:
            patterns.append(f"近期常跳过：{'、'.join(history.skipped_meals)}")

        # Calorie trend
        if history.avg_daily_kcal is not None:
            deviation = (history.avg_daily_kcal - daily_kcal_target) / daily_kcal_target * 100
            if deviation > 20:
                patterns.append(f"近期热量摄入偏高（平均 {history.avg_daily_kcal:.0f} kcal，目标 {daily_kcal_target} kcal）")
            elif deviation < -20:
                patterns.append(f"近期热量摄入偏低（平均 {history.avg_daily_kcal:.0f} kcal，目标 {daily_kcal_target} kcal）")

        # Protein check
        if history.avg_protein_g is not None:
            min_protein = daily_kcal_target * 0.15 / 4  # 15% minimum
            if history.avg_protein_g < min_protein:
                patterns.append(f"近期蛋白质摄入偏低，建议增加优质蛋白")

        # Food variety
        unique_foods = len(history.recent_food_names)
        if unique_foods < 8:
            patterns.append(f"近3天仅摄入 {unique_foods} 种食物，种类偏少")

        result["pattern_insights"] = patterns

        # --- 4. Nutrition gaps from history ---
        gaps = list(history.nutrition_gaps) if history.nutrition_gaps else []
        result["gaps"] = gaps

        # --- 5. Build history context prompt ---
        prompt_parts = []

        if result["avoided_foods"]:
            prompt_parts.append(f"⚠️ **必须避免的食物**（近3天已吃过或被用户标记不喜欢）：{', '.join(list(avoided)[:15])}")

        if result["liked_foods"]:
            prompt_parts.append(f"❤️ **用户偏好的食物**：{', '.join(result['liked_foods'][:10])}")

        if patterns:
            prompt_parts.append("📊 **饮食模式洞察**：")
            prompt_parts.extend(f"  - {p}" for p in patterns)

        if gaps:
            prompt_parts.append("🔍 **营养缺口**：")
            prompt_parts.extend(f"  - {g}" for g in gaps)

        if history.common_meal_types:
            prompt_parts.append(f"🍽️ **常吃餐次**：{'、'.join(history.common_meal_types)}")

        result["history_context_prompt"] = "\n".join(prompt_parts) if prompt_parts else "无特殊历史限制。"

        return result

    def _meal_kcal_target(self, meal_type: str, daily_target: int) -> int:
        """Calculate the recommended kcal for a specific meal type."""
        pct = self.MEAL_KCAL_PCT.get(meal_type, 0.28)
        return max(100, round(daily_target * pct))


# Singleton
history_analyzer = HistoryAnalyzer()
