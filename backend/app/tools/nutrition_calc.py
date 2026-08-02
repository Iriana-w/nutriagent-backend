"""
NutriAgent Backend — Nutrition Calculator Tool.

Provides macro/micro nutrient calculation utilities used by agents.
"""

from __future__ import annotations

from typing import TypedDict


class MacroTargets(TypedDict):
    """Daily macronutrient targets in grams."""

    protein_g: float
    fat_g: float
    carbs_g: float
    fiber_g: float


class NutritionCalculator:
    """Stateless nutrition calculation utilities."""

    # Calories per gram
    KCAL_PER_G_PROTEIN = 4.0
    KCAL_PER_G_FAT = 9.0
    KCAL_PER_G_CARBS = 4.0
    KCAL_PER_G_FIBER = 2.0

    # Activity multipliers for TDEE from BMR
    ACTIVITY_MULTIPLIERS = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9,
    }

    @classmethod
    def calc_bmi(cls, weight_kg: float, height_cm: float) -> float:
        """BMI = weight(kg) / height(m)^2"""
        if height_cm <= 0 or weight_kg <= 0:
            return 0.0
        height_m = height_cm / 100.0
        return round(weight_kg / (height_m * height_m), 1)

    @classmethod
    def calc_bmr(cls, weight_kg: float, height_cm: float, age: int, gender: str) -> float:
        """Mifflin-St Jeor BMR formula."""
        if gender == "male":
            return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
        elif gender == "female":
            return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
        else:
            return 10 * weight_kg + 6.25 * height_cm - 5 * age

    @classmethod
    def calc_tdee(cls, bmr: float, activity_level: str) -> float:
        """Total Daily Energy Expenditure from BMR."""
        multiplier = cls.ACTIVITY_MULTIPLIERS.get(activity_level, 1.2)
        return round(bmr * multiplier, 0)

    @classmethod
    def calc_macro_targets(
        cls,
        daily_kcal_target: float,
        *,
        protein_pct: float = 20,
        fat_pct: float = 30,
        carbs_pct: float = 50,
        fiber_target_g: float = 25,
    ) -> MacroTargets:
        """Calculate daily macro targets in grams from calorie target and percentages."""
        protein_kcal = daily_kcal_target * protein_pct / 100
        fat_kcal = daily_kcal_target * fat_pct / 100
        carbs_kcal = daily_kcal_target * carbs_pct / 100

        return MacroTargets(
            protein_g=round(protein_kcal / cls.KCAL_PER_G_PROTEIN, 1),
            fat_g=round(fat_kcal / cls.KCAL_PER_G_FAT, 1),
            carbs_g=round(carbs_kcal / cls.KCAL_PER_G_CARBS, 1),
            fiber_g=fiber_target_g,
        )

    @classmethod
    def calc_serving_nutrition(
        cls,
        per_100g_values: dict[str, float],
        serving_size_g: float,
    ) -> dict[str, float]:
        """Convert per-100g nutrition to actual serving size."""
        ratio = serving_size_g / 100.0
        return {
            key: round(value * ratio, 2) if value else 0.0
            for key, value in per_100g_values.items()
        }

    @classmethod
    def calc_caffeine_reduction_plan(cls, current_mg: int, target_mg: int, days: int = 14) -> list[int]:
        """Generate a linear caffeine tapering plan."""
        if days <= 0 or current_mg <= target_mg:
            return [target_mg]
        step = (current_mg - target_mg) / days
        return [max(round(current_mg - step * day), target_mg) for day in range(days + 1)]


# Singleton
nutrition_calc = NutritionCalculator()
