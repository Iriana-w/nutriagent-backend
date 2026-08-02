"""
NutriAgent Backend — Validation Node.

Post-generation validation of LLM recommendations:
- Nutritional reasonability check
- User constraint compliance (allergens, budget, diet types)
- Diversity check (no repeats from recent history)
- Calorie target alignment
"""

from __future__ import annotations

from app.agents.state import RecommendationState


class Validator:
    """Validates AI-generated recommendations for safety and compliance."""

    async def validate(self, state: RecommendationState) -> RecommendationState:
        """
        Run all validation checks on the generated recommendation.
        Sets validation_passed, warnings, and errors on state.
        """
        warnings: list[str] = []
        errors: list[str] = []

        items = state.items
        if not items:
            errors.append("推荐结果为空——没有生成任何食物推荐")
            state.validation_errors = errors
            state.validation_passed = False
            return state

        # --- 1. Allergen Check ---
        self._check_allergens(state, warnings, errors)

        # --- 2. Diet Type Check ---
        self._check_diet_types(state, warnings, errors)

        # --- 3. Calorie Reasonability ---
        self._check_calories(state, warnings, errors)

        # --- 4. Macro Balance ---
        self._check_macro_balance(state, warnings, errors)

        # --- 5. Budget Check ---
        self._check_budget(state, warnings, errors)

        # --- 6. Diversity Check ---
        self._check_diversity(state, warnings)

        # --- 7. Blacklist Check ---
        self._check_blacklist(state, warnings, errors)

        state.validation_warnings = warnings
        state.validation_errors = errors
        state.validation_passed = len(errors) == 0

        return state

    def _check_allergens(self, state: RecommendationState, warnings: list, errors: list) -> None:
        """Check for user allergen violations."""
        allergens = {
            a.get("allergen", "").lower()
            for a in state.user_context.get("allergens", [])
        }
        if not allergens:
            return

        for item in state.items:
            food_name = item.get("food_name", "").lower()
            for allergen in allergens:
                if allergen and allergen in food_name:
                    errors.append(f"食物 '{item.get('food_name')}' 包含过敏源 '{allergen}'！必须移除。")

    def _check_diet_types(self, state: RecommendationState, warnings: list, errors: list) -> None:
        """Check diet type compliance (vegan/vegetarian/etc)."""
        diet_types = state.user_context.get("diet_types", [])
        if not diet_types:
            return

        non_vegan_keywords = ["肉", "鱼", "虾", "蟹", "蛋", "奶", "鸡", "鸭", "猪", "牛", "羊", "贝", "蚝"]
        non_vegetarian_keywords = ["肉", "鱼", "虾", "蟹", "鸡", "鸭", "猪", "牛", "羊", "贝", "蚝"]

        for item in state.items:
            food_name = item.get("food_name", "")
            if "vegan" in diet_types:
                for kw in non_vegan_keywords:
                    if kw in food_name:
                        errors.append(f"食物 '{food_name}' 不符合纯素饮食。")
                        break
            elif "vegetarian" in diet_types:
                for kw in non_vegetarian_keywords:
                    if kw in food_name:
                        errors.append(f"食物 '{food_name}' 不符合素食（蛋奶）饮食。")
                        break

    def _check_calories(self, state: RecommendationState, warnings: list, errors: list) -> None:
        """Check if total calories are reasonable for the meal type."""
        total_kcal = sum(
            item.get("estimated_kcal", 0) or 0 for item in state.items
        )
        daily_target = state.user_context.get("daily_kcal_target", 2000)

        # Expected kcal per meal type
        expected_ranges = {
            "breakfast": (daily_target * 0.20, daily_target * 0.35),
            "lunch": (daily_target * 0.30, daily_target * 0.45),
            "dinner": (daily_target * 0.20, daily_target * 0.35),
            "snack": (50, 300),
            "late_night": (50, 300),
        }

        meal = state.meal_type
        if meal in expected_ranges:
            lo, hi = expected_ranges[meal]
            if total_kcal < lo * 0.5:
                warnings.append(f"热量偏低 ({total_kcal:.0f}kcal, 预期 {lo:.0f}-{hi:.0f}kcal)")
            elif total_kcal > hi * 1.5:
                warnings.append(f"热量偏高 ({total_kcal:.0f}kcal, 预期 {lo:.0f}-{hi:.0f}kcal)")

    def _check_macro_balance(self, state: RecommendationState, warnings: list, errors: list) -> None:
        """Check basic macronutrient balance."""
        total_protein = sum(item.get("estimated_protein_g", 0) or 0 for item in state.items)
        total_fat = sum(item.get("estimated_fat_g", 0) or 0 for item in state.items)
        total_carbs = sum(item.get("estimated_carbs_g", 0) or 0 for item in state.items)

        if state.meal_type in ("breakfast", "lunch", "dinner"):
            if total_protein < 10:
                warnings.append(f"蛋白质偏低 ({total_protein:.0f}g)，建议增加蛋白质来源")
            if total_fat > 40:
                warnings.append(f"脂肪偏高 ({total_fat:.0f}g)，建议减少油炸食品")

    def _check_budget(self, state: RecommendationState, warnings: list, errors: list) -> None:
        """Check budget compliance."""
        budget_cent = state.budget_cent or state.user_context.get("budget_per_meal")
        if budget_cent:
            # Items from delivery have price info
            pass  # Placeholder — requires actual price data

    def _check_diversity(self, state: RecommendationState, warnings: list) -> None:
        """Check that recommended foods aren't repeats from recent history."""
        recent_foods = set()
        for meal in state.user_context.get("recent_meals", [])[:6]:
            for food in meal.get("foods", []):
                recent_foods.add(food.lower())

        repeats = []
        for item in state.items:
            food_name = item.get("food_name", "").lower()
            if food_name in recent_foods or any(
                recent in food_name or food_name in recent
                for recent in recent_foods
            ):
                repeats.append(item.get("food_name", ""))

        if repeats:
            warnings.append(f"以下食物与近2天记录重复：{', '.join(repeats)}")

    def _check_blacklist(self, state: RecommendationState, warnings: list, errors: list) -> None:
        """Check user food blacklist."""
        blacklist = [
            b.lower() for b in state.user_context.get("food_blacklist", [])
        ]
        exclude = [e.lower() for e in state.exclude_foods]

        for item in state.items:
            food_name = item.get("food_name", "").lower()
            for banned in blacklist + exclude:
                if banned and banned in food_name:
                    errors.append(f"食物 '{item.get('food_name')}' 在用户黑名单中！必须移除。")
                    break
