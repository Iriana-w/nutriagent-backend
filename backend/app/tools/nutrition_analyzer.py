"""
NutriAgent Backend — Nutrition Analyzer Tool.

Core scoring algorithms for the Nutrition Agent.
Implements multi-dimensional diet quality scoring based on
Chinese Dietary Guidelines and programmer-specific health factors.

Scoring Dimensions (6 dimensions, weighted):
1. Calorie Balance     (25%) — kcal intake vs target
2. Macro Balance       (25%) — protein/fat/carbs ratio
3. Food Variety        (15%) — number of unique foods
4. Meal Timing         (10%) — meal distribution & timing
5. Food Quality        (15%) — processed food ratio, fiber, sodium
6. Programmer Health   (10%) — eye health, caffeine, micronutrients
"""

from __future__ import annotations

from app.schemas.nutrition_agent import (
    DimensionScore,
    MacroBalance,
    MealTimingAnalysis,
    MicronutrientGap,
)
from app.tools.nutrition_calc import NutritionCalculator

calc = NutritionCalculator()


# ============================================================================
# Dimension 1: Calorie Balance (weight: 25%)
# ============================================================================


def score_calorie_balance(total_kcal: float, kcal_target: float) -> DimensionScore:
    """
    Score how well the day's calories match the target.
    100 = within 5% of target, 0 = >50% off.
    """
    if kcal_target <= 0:
        kcal_target = 2000

    deviation_pct = abs(total_kcal - kcal_target) / kcal_target

    if deviation_pct <= 0.05:
        score = 100.0
        grade = "A"
        details = [f"热量摄入 {total_kcal:.0f} kcal，完美匹配目标 {kcal_target:.0f} kcal"]
        suggestions = ["继续保持！"]
    elif deviation_pct <= 0.10:
        score = 90.0
        grade = "A"
        details = [f"热量摄入 {total_kcal:.0f} kcal，接近目标 {kcal_target:.0f} kcal（偏差 {deviation_pct:.0%}）"]
        suggestions = ["微调份量即可达到完美"]
    elif deviation_pct <= 0.20:
        score = 75.0
        grade = "B"
        direction = "偏高" if total_kcal > kcal_target else "偏低"
        details = [f"热量摄入{direction}：{total_kcal:.0f} vs 目标 {kcal_target:.0f} kcal（偏差 {deviation_pct:.0%}）"]
        suggestions = [
            "减少主食份量，增加蔬菜占比" if total_kcal > kcal_target
            else "增加一餐或加大蛋白质份量"
        ]
    elif deviation_pct <= 0.35:
        score = 50.0
        grade = "C"
        direction = "偏高" if total_kcal > kcal_target else "偏低"
        details = [f"热量摄入明显{direction}：{total_kcal:.0f} vs 目标 {kcal_target:.0f} kcal"]
        suggestions = [
            "重新评估每餐份量，减少高热量密度食物" if total_kcal > kcal_target
            else "增加营养密度高的食物：坚果、鸡蛋、全脂奶制品"
        ]
    elif deviation_pct <= 0.50:
        score = 25.0
        grade = "D"
        details = [f"热量摄入严重偏离目标：{total_kcal:.0f} vs {kcal_target:.0f} kcal"]
        suggestions = ["需要大幅调整饮食结构，建议咨询营养师"]
    else:
        score = 10.0
        grade = "F"
        details = [f"热量摄入极度偏离目标：{total_kcal:.0f} vs {kcal_target:.0f} kcal"]
        suggestions = ["饮食结构需要根本性改变，强烈建议咨询营养师"]

    return DimensionScore(
        dimension="热量平衡",
        score=score,
        weight=0.25,
        weighted_score=score * 0.25,
        grade=grade,
        details=details,
        suggestions=suggestions,
    )


# ============================================================================
# Dimension 2: Macro Balance (weight: 25%)
# ============================================================================


def score_macro_balance(
    total_protein_g: float, total_fat_g: float, total_carbs_g: float,
    total_fiber_g: float, total_kcal: float,
    target_protein_pct: float, target_fat_pct: float, target_carbs_pct: float,
) -> tuple[DimensionScore, MacroBalance]:
    """
    Score macronutrient balance. Checks ratio alignment and fiber adequacy.
    """
    macro_kcal = total_protein_g * 4 + total_fat_g * 9 + total_carbs_g * 4
    if macro_kcal <= 0:
        macro_kcal = 1

    protein_pct = round(total_protein_g * 400 / macro_kcal, 1)
    fat_pct = round(total_fat_g * 900 / macro_kcal, 1)
    carbs_pct = round(total_carbs_g * 400 / macro_kcal, 1)

    protein_target_g = round(target_protein_pct / 100 * total_kcal / 4, 1) if total_kcal > 0 else None
    fat_target_g = round(target_fat_pct / 100 * total_kcal / 9, 1) if total_kcal > 0 else None
    carbs_target_g = round(target_carbs_pct / 100 * total_kcal / 4, 1) if total_kcal > 0 else None

    # Sub-scores
    protein_dev = abs(protein_pct - target_protein_pct) / max(target_protein_pct, 1)
    fat_dev = abs(fat_pct - target_fat_pct) / max(target_fat_pct, 1)
    carbs_dev = abs(carbs_pct - target_carbs_pct) / max(target_carbs_pct, 1)

    protein_score = max(0, 100 - protein_dev * 100)
    fat_score = max(0, 100 - fat_dev * 100)
    carbs_score = max(0, 100 - carbs_dev * 100)
    fiber_score = min(100, total_fiber_g / 25 * 100) if total_fiber_g >= 0 else 0

    # Weighted composite
    score = protein_score * 0.30 + fat_score * 0.25 + carbs_score * 0.25 + fiber_score * 0.20

    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 55:
        grade = "C"
    elif score >= 35:
        grade = "D"
    else:
        grade = "F"

    protein_status = "low" if protein_pct < target_protein_pct - 5 else ("high" if protein_pct > target_protein_pct + 5 else "normal")
    fat_status = "low" if fat_pct < target_fat_pct - 5 else ("high" if fat_pct > target_fat_pct + 5 else "normal")
    carbs_status = "low" if carbs_pct < target_carbs_pct - 5 else ("high" if carbs_pct > target_carbs_pct + 5 else "normal")
    fiber_status = "low" if total_fiber_g < 20 else ("high" if total_fiber_g > 40 else "normal")

    details = [
        f"蛋白质 {total_protein_g:.1f}g ({protein_pct}%) — {'✅' if protein_status == 'normal' else '⚠️'}{protein_status}",
        f"脂肪 {total_fat_g:.1f}g ({fat_pct}%) — {'✅' if fat_status == 'normal' else '⚠️'}{fat_status}",
        f"碳水 {total_carbs_g:.1f}g ({carbs_pct}%) — {'✅' if carbs_status == 'normal' else '⚠️'}{carbs_status}",
        f"膳食纤维 {total_fiber_g:.1f}g — {'✅' if fiber_status == 'normal' else '⚠️'}{fiber_status}",
    ]

    suggestions = []
    if protein_status == "low":
        suggestions.append("增加优质蛋白：鸡胸肉、鱼、豆腐、鸡蛋、希腊酸奶")
    if protein_status == "high":
        suggestions.append("蛋白质摄入偏高，注意均衡碳水摄入")
    if fat_status == "high":
        suggestions.append("减少油炸食品和肥肉，选择蒸煮烹饪方式")
    if fat_status == "low":
        suggestions.append("增加健康脂肪：坚果、牛油果、橄榄油、深海鱼")
    if fiber_status == "low":
        suggestions.append("多吃蔬菜、水果、全谷物和杂豆以增加膳食纤维")
    if carbs_status == "low":
        suggestions.append("适当增加全谷物主食（燕麦、糙米、全麦面包）")

    macro_balance = MacroBalance(
        protein_g=round(total_protein_g, 1),
        fat_g=round(total_fat_g, 1),
        carbs_g=round(total_carbs_g, 1),
        fiber_g=round(total_fiber_g, 1),
        protein_pct=protein_pct,
        fat_pct=fat_pct,
        carbs_pct=carbs_pct,
        protein_target_g=protein_target_g,
        fat_target_g=fat_target_g,
        carbs_target_g=carbs_target_g,
        fiber_target_g=25,
        protein_status=protein_status,
        fat_status=fat_status,
        carbs_status=carbs_status,
        fiber_status=fiber_status,
    )

    return DimensionScore(
        dimension="宏量营养素平衡",
        score=round(score, 1),
        weight=0.25,
        weighted_score=round(score * 0.25, 1),
        grade=grade,
        details=details,
        suggestions=suggestions,
    ), macro_balance


# ============================================================================
# Dimension 3: Food Variety (weight: 15%)
# ============================================================================


def score_food_variety(unique_food_names: list[str]) -> DimensionScore:
    """
    Score food diversity. Chinese Dietary Guidelines recommend
    12+ different foods per day, 25+ per week.
    """
    count = len(unique_food_names)

    if count >= 15:
        score = 100.0
        grade = "A"
        details = [f"今日摄入 {count} 种不同食物，食物多样性优秀！超过推荐量12种"]
        suggestions = ["保持多样化的饮食习惯"]
    elif count >= 12:
        score = 90.0
        grade = "A"
        details = [f"今日摄入 {count} 种不同食物，达到推荐量12种"]
        suggestions = ["可以再增加2-3种蔬菜或水果"]
    elif count >= 9:
        score = 70.0
        grade = "B"
        details = [f"今日摄入 {count} 种食物，未达到推荐量12种"]
        suggestions = ["尝试每天加入不同颜色的蔬菜，增加食物多样性"]
    elif count >= 6:
        score = 50.0
        grade = "C"
        details = [f"今日仅摄入 {count} 种食物，种类偏少"]
        suggestions = ["每天应有谷薯、蔬果、肉蛋奶、豆类、坚果等多种类食物"]
    elif count >= 3:
        score = 30.0
        grade = "D"
        details = [f"今日仅摄入 {count} 种食物，严重不足"]
        suggestions = ["大幅增加蔬菜和水果种类，尝试新的蛋白质来源"]
    else:
        score = 10.0
        grade = "F"
        details = [f"今日仅摄入 {count} 种食物，极度单一"]
        suggestions = ["饮食极度单一，营养缺乏风险高。建议每天至少12种食物"]

    return DimensionScore(
        dimension="食物多样性",
        score=score,
        weight=0.15,
        weighted_score=score * 0.15,
        grade=grade,
        details=details,
        suggestions=suggestions,
    )


# ============================================================================
# Dimension 4: Meal Timing (weight: 10%)
# ============================================================================


def score_meal_timing(meals: list[dict]) -> tuple[DimensionScore, MealTimingAnalysis]:
    """
    Score meal timing and distribution.
    Checks breakfast, late-night eating, meal gaps, and calorie distribution.
    """
    from datetime import time

    meal_times: dict[str, list[dict]] = {}
    for m in meals:
        mt = m.get("meal_type", "snack")
        meal_times.setdefault(mt, []).append(m)

    breakfast_kcal = sum(
        sum(item.get("energy_kcal", 0) for item in m.get("items", []))
        for m in meal_times.get("breakfast", [])
    )
    lunch_kcal = sum(
        sum(item.get("energy_kcal", 0) for item in m.get("items", []))
        for m in meal_times.get("lunch", [])
    )
    dinner_kcal = sum(
        sum(item.get("energy_kcal", 0) for item in m.get("items", []))
        for m in meal_times.get("dinner", [])
    )
    snack_kcal = sum(
        sum(item.get("energy_kcal", 0) for item in m.get("items", []))
        for m in meal_times.get("snack", [])
    )
    late_night_kcal = sum(
        sum(item.get("energy_kcal", 0) for item in m.get("items", []))
        for m in meal_times.get("late_night", [])
    )

    total_meal_kcal = breakfast_kcal + lunch_kcal + dinner_kcal + snack_kcal + late_night_kcal
    if total_meal_kcal <= 0:
        total_meal_kcal = 1

    has_breakfast = len(meal_times.get("breakfast", [])) > 0
    has_late_night = len(meal_times.get("late_night", [])) > 0
    meal_count = len(meals)

    details = []
    score = 100.0

    # Breakfast check (critical)
    if not has_breakfast:
        score -= 30
        details.append("❌ 未吃早餐——跳过早餐会降低代谢率，影响上午工作效率")
    else:
        details.append("✅ 有吃早餐，良好习惯！")

    # Late night check
    if has_late_night:
        if late_night_kcal > 300:
            score -= 20
            details.append(f"⚠️ 深夜进食 {late_night_kcal:.0f} kcal（偏多），可能影响睡眠和次日血糖")
        elif late_night_kcal > 150:
            score -= 10
            details.append(f"⚠️ 深夜加餐 {late_night_kcal:.0f} kcal，注意控制在200kcal以内")
        else:
            details.append(f"✅ 深夜加餐 {late_night_kcal:.0f} kcal，份量合理")

    # Meal count
    if meal_count >= 4:
        details.append("✅ 餐次分布良好（4餐以上），有助于稳定血糖")
    elif meal_count >= 3:
        details.append("✅ 三餐规律")
    elif meal_count == 2:
        score -= 15
        details.append("⚠️ 仅2餐——长时间空腹可能导致下一餐暴食")
    else:
        score -= 25
        details.append("❌ 仅1餐或记录不完整")

    # Calorie distribution
    bf_pct = round(breakfast_kcal / total_meal_kcal * 100, 1)
    lu_pct = round(lunch_kcal / total_meal_kcal * 100, 1)
    dn_pct = round(dinner_kcal / total_meal_kcal * 100, 1)

    if has_breakfast and bf_pct < 15:
        score -= 10
        details.append(f"⚠️ 早餐热量偏低 ({bf_pct}%)，建议占全天25-30%")
    if dn_pct > 45:
        score -= 10
        details.append(f"⚠️ 晚餐热量偏高 ({dn_pct}%)，建议控制在25-30%")

    score = max(0, min(100, score))

    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 55:
        grade = "C"
    elif score >= 35:
        grade = "D"
    else:
        grade = "F"

    suggestions = []
    if not has_breakfast:
        suggestions.append("每天必须吃早餐！即使简单如牛奶+全麦面包+一个鸡蛋也好")
    if has_late_night:
        suggestions.append("尽量避免深夜进食。如需加班，选择水果、酸奶等轻食")
    if meal_count < 3:
        suggestions.append("保持三餐规律，可在上午和下午各加一次健康零食")

    timing_analysis = MealTimingAnalysis(
        meal_count=meal_count,
        breakfast_kcal_pct=bf_pct,
        lunch_kcal_pct=lu_pct,
        dinner_kcal_pct=dn_pct,
        snack_kcal_pct=round(snack_kcal / total_meal_kcal * 100, 1),
        late_night_kcal=late_night_kcal,
        has_breakfast=has_breakfast,
        has_late_night=has_late_night,
        timing_score=score,
        timing_notes=details,
    )

    return DimensionScore(
        dimension="进餐节律",
        score=round(score, 1),
        weight=0.10,
        weighted_score=round(score * 0.10, 1),
        grade=grade,
        details=details,
        suggestions=suggestions,
    ), timing_analysis


# ============================================================================
# Dimension 5: Food Quality (weight: 15%)
# ============================================================================


def score_food_quality(
    processed_pct: float, total_sodium_mg: float, total_fiber_g: float,
    total_sugar_g: float, total_kcal: float,
) -> DimensionScore:
    """
    Score food quality based on processing, sodium, fiber, and sugar.
    """
    score = 100.0
    details = []

    # Processed food ratio
    if processed_pct > 50:
        score -= 30
        details.append(f"❌ 加工食品占比 {processed_pct:.0f}%——过高！尽量选择天然食材")
    elif processed_pct > 30:
        score -= 15
        details.append(f"⚠️ 加工食品占比 {processed_pct:.0f}%，建议减少方便面、速食、零食")
    elif processed_pct > 10:
        score -= 5
        details.append(f"⚡ 加工食品占比 {processed_pct:.0f}%，还算不错")
    else:
        details.append(f"✅ 加工食品占比 {processed_pct:.0f}%，以天然食物为主")

    # Sodium (target: <2000mg/day)
    if total_sodium_mg > 3000:
        score -= 25
        details.append(f"❌ 钠摄入 {total_sodium_mg:.0f}mg——严重超标（推荐<2000mg），高血压风险")
    elif total_sodium_mg > 2000:
        score -= 15
        details.append(f"⚠️ 钠摄入 {total_sodium_mg:.0f}mg——超过推荐量2000mg，注意少盐")
    elif total_sodium_mg > 1000:
        score -= 5
        details.append(f"⚡ 钠摄入 {total_sodium_mg:.0f}mg，在合理范围内")
    else:
        details.append(f"✅ 钠摄入 {total_sodium_mg:.0f}mg，控制良好")

    # Fiber
    if total_fiber_g < 15:
        score -= 10
        details.append(f"⚠️ 膳食纤维仅 {total_fiber_g:.1f}g（推荐25-30g），增加蔬菜和全谷物")
    else:
        details.append(f"✅ 膳食纤维 {total_fiber_g:.1f}g")

    # Added sugar warning
    if total_sugar_g > 50:
        score -= 15
        details.append(f"⚠️ 糖摄入 {total_sugar_g:.0f}g（推荐<50g），注意含糖饮料和零食")
    elif total_sugar_g > 25:
        score -= 5
        details.append(f"⚡ 糖摄入 {total_sugar_g:.0f}g")

    score = max(0, min(100, score))

    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 55:
        grade = "C"
    elif score >= 35:
        grade = "D"
    else:
        grade = "F"

    suggestions = []
    if processed_pct > 30:
        suggestions.append("减少方便面、速食、外卖油炸食品，自己简单烹饪更健康")
    if total_sodium_mg > 2000:
        suggestions.append("少放盐和酱油，避免咸菜和加工肉制品，多利用香料调味")
    if total_sugar_g > 50:
        suggestions.append("用水果替代甜点和含糖饮料，注意隐藏糖（酸奶、酱料）")

    return DimensionScore(
        dimension="食物质量",
        score=round(score, 1),
        weight=0.15,
        weighted_score=round(score * 0.15, 1),
        grade=grade,
        details=details,
        suggestions=suggestions,
    )


# ============================================================================
# Dimension 6: Programmer Health (weight: 10%)
# ============================================================================


def score_programmer_health(
    total_caffeine_mg: float, total_sodium_mg: float,
    has_breakfast: bool, processed_pct: float,
    estimated_lutein_ug: float, estimated_omega3_g: float,
    estimated_vitamin_a_ug: float, estimated_magnesium_mg: float,
    estimated_iron_mg: float,
) -> tuple[DimensionScore, list[MicronutrientGap]]:
    """
    Score programmer-specific health factors:
    - Caffeine management
    - Eye health nutrients (lutein, vitamin A)
    - Brain health (omega-3)
    - Stress/sleep support (magnesium)
    - Sedentary risks (iron, sodium)
    """
    score = 100.0
    details = []
    gaps: list[MicronutrientGap] = []

    # Caffeine
    if total_caffeine_mg > 600:
        score -= 25
        details.append(f"❌ 咖啡因 {total_caffeine_mg:.0f}mg——严重超标（<400mg），心悸/失眠风险高")
    elif total_caffeine_mg > 400:
        score -= 15
        details.append(f"⚠️ 咖啡因 {total_caffeine_mg:.0f}mg——超过推荐上限400mg（≈2杯中杯美式）")
    elif total_caffeine_mg > 200:
        score -= 5
        details.append(f"⚡ 咖啡因 {total_caffeine_mg:.0f}mg，注意下午2点后不再摄入")
    else:
        details.append(f"✅ 咖啡因 {total_caffeine_mg:.0f}mg，在安全范围内")

    # Eye health — lutein
    if estimated_lutein_ug < 3000:
        severity = "critical" if estimated_lutein_ug < 1000 else "moderate"
        score -= 10 if severity == "critical" else 5
        details.append(f"⚠️ 叶黄素摄入偏低——程序员每日用眼10h+，需要至少6mg叶黄素")
        gaps.append(MicronutrientGap(
            nutrient="叶黄素", current_value=estimated_lutein_ug, target_value=6000,
            unit="μg", severity=severity,
            food_sources=["菠菜", "羽衣甘蓝", "西兰花", "玉米", "蛋黄", "南瓜"],
        ))
    else:
        details.append("✅ 叶黄素摄入充足，护眼良好")

    # Omega-3 (brain)
    if estimated_omega3_g < 1.0:
        score -= 10
        details.append("⚠️ Omega-3 摄入不足——对大脑和抗炎至关重要")
        gaps.append(MicronutrientGap(
            nutrient="Omega-3", current_value=estimated_omega3_g, target_value=2.5,
            unit="g", severity="moderate",
            food_sources=["三文鱼", "沙丁鱼", "核桃", "亚麻籽", "奇亚籽"],
        ))

    # Magnesium
    if estimated_magnesium_mg < 200:
        score -= 8
        details.append("⚠️ 镁摄入偏低——影响睡眠质量和压力管理")
        gaps.append(MicronutrientGap(
            nutrient="镁", current_value=estimated_magnesium_mg, target_value=330,
            unit="mg", severity="moderate",
            food_sources=["坚果", "深绿蔬菜", "黑巧克力", "香蕉", "牛油果"],
        ))

    # Iron
    if estimated_iron_mg < 8:
        score -= 8
        details.append("⚠️ 铁摄入偏低——可能导致疲劳乏力")
        gaps.append(MicronutrientGap(
            nutrient="铁", current_value=estimated_iron_mg, target_value=15,
            unit="mg", severity="mild",
            food_sources=["红肉", "菠菜", "黑木耳", "动物肝脏", "豆类"],
        ))

    score = max(0, min(100, score))

    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 55:
        grade = "C"
    elif score >= 35:
        grade = "D"
    else:
        grade = "F"

    suggestions = []
    if total_caffeine_mg > 400:
        suggestions.append("逐步减少咖啡因：每天少喝半杯，用路易波士茶或柠檬水替代")
    if estimated_lutein_ug < 3000:
        suggestions.append("每天吃一份深绿色蔬菜（菠菜/西兰花）+ 一个鸡蛋黄，补充叶黄素")
    if estimated_omega3_g < 1.0:
        suggestions.append("每周吃2-3次深海鱼（三文鱼/沙丁鱼），或每日补充鱼油")
    if estimated_magnesium_mg < 200:
        suggestions.append("每天一小把坚果 + 黑巧克力作为下午加餐，补充镁元素")

    return DimensionScore(
        dimension="程序员健康专项",
        score=round(score, 1),
        weight=0.10,
        weighted_score=round(score * 0.10, 1),
        grade=grade,
        details=details,
        suggestions=suggestions,
    ), gaps


# ============================================================================
# Composite Health Score
# ============================================================================


def compute_health_score(dimensions: list[DimensionScore]) -> tuple[float, str, str]:
    """
    Compute the weighted composite health score and grade.
    Returns (score, grade, summary).
    """
    total = sum(d.weighted_score for d in dimensions)

    if total >= 90:
        grade = "A"
        summary = "太棒了！你的饮食非常健康，营养均衡、食物多样。保持下去！"
    elif total >= 75:
        grade = "B"
        summary = "整体不错！有几个方面可以微调，让你的饮食更上一层楼。"
    elif total >= 60:
        grade = "C"
        summary = "饮食有较大改善空间。建议关注评分较低的维度，逐步调整饮食习惯。"
    elif total >= 40:
        grade = "D"
        summary = "饮食结构需要较大调整。建议从最薄弱的1-2个维度开始改善。"
    else:
        grade = "F"
        summary = "你的饮食需要根本性改变。强烈建议参考以下建议并咨询专业营养师。"

    return round(total, 1), grade, summary
