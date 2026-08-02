"""
NutriAgent Backend — Nutrition Knowledge Base Tool.

Provides programmatic access to nutrition guidelines and knowledge
for the AI recommendation engine's RAG layer.
"""

from __future__ import annotations

# ============================================================================
# Chinese Dietary Guidelines (2022) — key facts
# ============================================================================

DIETARY_GUIDELINES = {
    "general": [
        "食物多样，谷类为主：每天摄入谷薯类食物250-400g",
        "吃动平衡，健康体重：每周至少5天中等强度运动，累计150分钟以上",
        "多吃蔬果、奶类、大豆：每天蔬菜300-500g，水果200-350g",
        "适量吃鱼、禽、蛋、瘦肉：每周鱼280-525g，畜禽肉280-525g，蛋类280-350g",
        "少盐少油，控糖限酒：每天食盐不超过5g，烹饪油25-30g，添加糖<50g",
        "杜绝浪费，兴新食尚：按需备餐，分餐公筷",
    ],
    "programmer_focus": [
        "护眼食物：深色蔬菜（菠菜、西兰花）、胡萝卜、蓝莓、鸡蛋黄（富含叶黄素和维生素A）",
        "Omega-3 来源：三文鱼、沙丁鱼、核桃、亚麻籽（抗炎、护脑）",
        "B族维生素：全谷物、瘦肉、蛋类（能量代谢、神经系统健康，久坐程序员的必需营养素）",
        "镁元素：坚果、深绿蔬菜、黑巧克力（缓解压力、改善睡眠质量）",
        "维生素D：蛋黄、蘑菇、多晒太阳（久坐室内程序员的常见缺乏）",
        "膳食纤维：燕麦、杂豆、蔬菜（预防久坐便秘）",
    ],
    "scenario_knowledge": {
        "overtime": [
            "熬夜时避免高GI食物，选择低GI的燕麦、全麦面包维持稳定血糖",
            "蛋白质零食（鸡蛋、希腊酸奶、毛豆）比碳水零食更能保持清醒",
            "夜宵热量控制在200-300kcal，避免影响睡眠",
            "补充水分，每小时一杯水，避免含糖饮料",
        ],
        "eye_care": [
            "叶黄素每日推荐摄入10mg，玉米黄质2mg",
            "维生素A 推荐每日800μg RAE（成年男性）",
            "Omega-3 DHA对视网膜健康至关重要",
            "避免高糖饮食加重眼疲劳",
        ],
        "hair_care": [
            "生物素（维生素B7）：鸡蛋、坚果、三文鱼",
            "锌：牡蛎、牛肉、南瓜籽",
            "铁：红肉、菠菜、黑木耳（缺铁性脱发常见于女性）",
            "蛋白质不足是脱发的常见营养原因",
        ],
        "caffeine_cut": [
            "咖啡因半衰期约5小时，下午2点后避免摄入含咖啡因饮品",
            "逐步减量比突然戒断更有效（每周减少10-20%）",
            "替代饮品：路易波士茶、洋甘菊茶、柠檬水、气泡水",
            "运动和水是天然提神方式",
        ],
        "energy_boost": [
            "复合碳水 + 蛋白质 + 健康脂肪是能量持久的黄金组合",
            "铁和B12缺乏是疲劳的常见营养原因",
            "少食多餐比大餐更能维持稳定血糖和精力",
            "早餐不可跳过，富含蛋白质的早餐能提升全天精力",
        ],
        "party_survival": [
            "聚餐前先吃一份沙拉或蔬菜汤增加饱腹感",
            "优先选择蒸、煮、凉拌的菜品，避免油炸和红烧",
            "饮料选无糖茶或苏打水，酒精适量（男性≤25g酒精/天，女性≤15g）",
            "一餐高热量不会毁掉整体饮食计划，下一餐回归正常即可",
        ],
    },
    "meal_timing": {
        "breakfast": "7:00-8:30，占全天热量25-30%，适量碳水+丰富蛋白",
        "lunch": "11:30-13:00，占全天热量35-40%，均衡三大营养素",
        "dinner": "18:00-19:30，占全天热量25-30%，轻碳水多蔬菜",
        "snack": "10:00 / 15:00 / 21:00前，每次100-200kcal",
    },
    "nutrient_rda": {
        "protein": "成年男性65g/天，女性55g/天",
        "fiber": "25-30g/天",
        "sodium": "<2000mg/天（约5g盐）",
        "caffeine": "<400mg/天（约2杯中杯美式）",
        "vitamin_a": "800μg RAE/天（男），700μg RAE/天（女）",
        "vitamin_c": "100mg/天",
        "calcium": "800mg/天",
        "iron": "12mg/天（男），20mg/天（女）",
        "magnesium": "330mg/天",
    },
}


def get_dietary_guidelines(category: str | None = None) -> dict:
    """Retrieve dietary guidelines by category. Returns all if category is None."""
    if category and category in DIETARY_GUIDELINES:
        return {category: DIETARY_GUIDELINES[category]}
    return DIETARY_GUIDELINES


def get_scenario_knowledge(scenario: str) -> list[str]:
    """Get nutrition knowledge specific to a scenario tag."""
    return DIETARY_GUIDELINES.get("scenario_knowledge", {}).get(scenario, [])


def get_programmer_nutrition_tips() -> list[str]:
    """Get nutrition tips specifically for programmers."""
    return DIETARY_GUIDELINES.get("programmer_focus", [])


def get_meal_timing_guidance(meal_type: str | None = None) -> dict:
    """Get recommended meal timing and calorie distribution."""
    timing = DIETARY_GUIDELINES.get("meal_timing", {})
    if meal_type and meal_type in timing:
        return {meal_type: timing[meal_type]}
    return timing


def format_knowledge_for_prompt(
    scenario: str | None = None,
    health_goals: list[str] | None = None,
    include_general: bool = True,
) -> str:
    """
    Format nutrition knowledge into a compact string for LLM prompt injection.
    This is the primary RAG output — concatenated knowledge snippets.
    """
    parts = []

    if include_general:
        parts.append("【中国居民膳食指南核心原则】")
        parts.extend(f"- {g}" for g in DIETARY_GUIDELINES["general"])

    parts.append("【程序员营养要点】")
    parts.extend(f"- {t}" for t in DIETARY_GUIDELINES["programmer_focus"])

    if scenario and scenario in DIETARY_GUIDELINES["scenario_knowledge"]:
        parts.append(f"【{scenario}场景营养建议】")
        parts.extend(f"- {s}" for s in DIETARY_GUIDELINES["scenario_knowledge"][scenario])

    if health_goals:
        parts.append("【用户健康目标相关营养知识】")
        for goal in health_goals:
            if goal in DIETARY_GUIDELINES.get("scenario_knowledge", {}):
                parts.extend(
                    f"- {s}"
                    for s in DIETARY_GUIDELINES["scenario_knowledge"][goal]
                )

    return "\n".join(parts)
