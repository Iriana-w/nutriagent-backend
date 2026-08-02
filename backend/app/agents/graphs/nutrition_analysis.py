"""
NutriAgent Backend — Nutrition Analysis Graph.

LangGraph workflow for analyzing a day's food record and producing
a comprehensive health score with AI-powered insights.

Pipeline (5 nodes):
  parse_input → calculate_metrics → evaluate_scoring → generate_insights → format_output

The analysis combines:
- Deterministic scoring algorithms (6 dimensions)
- LLM-generated insights and personalized suggestions
"""

from __future__ import annotations

import json
import time
from datetime import date

from langgraph.graph import END, StateGraph

from app.agents.base import BaseAgent
from app.agents.nutrition_state import NutritionAgentState
from app.schemas.nutrition_agent import (
    DimensionScore,
    FoodRecord,
    MealRecord,
    NutritionAnalysis,
)
from app.tools.nutrition_analyzer import (
    compute_health_score,
    score_calorie_balance,
    score_food_quality,
    score_food_variety,
    score_macro_balance,
    score_meal_timing,
    score_programmer_health,
)


# ============================================================================
# Node 1: Parse Input
# ============================================================================


async def parse_input(state: NutritionAgentState) -> NutritionAgentState:
    """Validate and normalize the FoodRecord into structured meal/food lists."""
    if state.food_record is None and not state.food_record_dict:
        state.error = "No FoodRecord provided"
        return state

    record = state.food_record
    if record is None:
        # Deserialize from dict
        try:
            record = FoodRecord(**state.food_record_dict)
            state.food_record = record
        except Exception as e:
            state.error = f"Invalid FoodRecord: {e}"
            return state

    # Extract all meals
    for meal in record.meals:
        meal_dict = {
            "meal_type": meal.meal_type,
            "meal_time": str(meal.meal_time) if meal.meal_time else None,
            "location": meal.location,
            "satiety_level": meal.satiety_level,
            "mood_before": meal.mood_before,
            "mood_after": meal.mood_after,
            "items": [],
        }
        for item in meal.items:
            item_dict = {
                "food_name": item.food_name,
                "food_id": str(item.food_id) if item.food_id else None,
                "serving_size_g": item.serving_size_g,
                "energy_kcal": item.energy_kcal,
                "protein_g": item.protein_g,
                "fat_g": item.fat_g,
                "carbs_g": item.carbs_g,
                "fiber_g": item.fiber_g,
                "sodium_mg": item.sodium_mg,
                "sugar_g": item.sugar_g,
                "caffeine_mg": item.caffeine_mg,
                "is_processed": item.is_processed,
            }
            meal_dict["items"].append(item_dict)
            state.all_food_items.append(item_dict)
        state.parsed_meals.append(meal_dict)

    # Set kcal target
    if record.user_profile and record.user_profile.daily_kcal_target:
        state.kcal_target = record.user_profile.daily_kcal_target
    else:
        state.kcal_target = 2000

    return state


# ============================================================================
# Node 2: Calculate Metrics
# ============================================================================


async def calculate_metrics(state: NutritionAgentState) -> NutritionAgentState:
    """Compute all nutritional metrics from the parsed food items."""
    if state.error:
        return state

    # Aggregate nutrition totals
    state.total_kcal = sum(item["energy_kcal"] for item in state.all_food_items)
    state.total_protein_g = sum(item["protein_g"] for item in state.all_food_items)
    state.total_fat_g = sum(item["fat_g"] for item in state.all_food_items)
    state.total_carbs_g = sum(item["carbs_g"] for item in state.all_food_items)
    state.total_fiber_g = sum(item["fiber_g"] for item in state.all_food_items)
    state.total_sodium_mg = sum(item["sodium_mg"] for item in state.all_food_items)
    state.total_sugar_g = sum(item.get("sugar_g", 0) for item in state.all_food_items)
    state.total_caffeine_mg = sum(item["caffeine_mg"] for item in state.all_food_items)

    # Food variety
    state.unique_food_names = list(set(
        item["food_name"] for item in state.all_food_items
    ))
    state.food_variety_count = len(state.unique_food_names)

    # Processed food ratio
    state.processed_food_count = sum(
        1 for item in state.all_food_items if item.get("is_processed", False)
    )
    total_items = len(state.all_food_items)
    state.processed_food_pct = round(
        state.processed_food_count / total_items * 100, 1
    ) if total_items > 0 else 0.0

    # Estimate micronutrients based on food names
    state.estimated_lutein_ug = _estimate_lutein(state.all_food_items)
    state.estimated_omega3_g = _estimate_omega3(state.all_food_items)
    state.estimated_vitamin_a_ug = _estimate_vitamin_a(state.all_food_items)
    state.estimated_vitamin_c_mg = _estimate_vitamin_c(state.all_food_items)
    state.estimated_calcium_mg = _estimate_calcium(state.all_food_items)
    state.estimated_iron_mg = _estimate_iron(state.all_food_items)
    state.estimated_magnesium_mg = _estimate_magnesium(state.all_food_items)

    return state


# ============================================================================
# Node 3: Evaluate Scoring
# ============================================================================


async def evaluate_scoring(state: NutritionAgentState) -> NutritionAgentState:
    """Run all 6 dimension scoring algorithms and compute the composite health score."""
    if state.error:
        return state

    record = state.food_record
    user_profile = record.user_profile if record else None

    target_protein_pct = user_profile.target_protein_pct if user_profile else 20
    target_fat_pct = user_profile.target_fat_pct if user_profile else 30
    target_carbs_pct = user_profile.target_carbs_pct if user_profile else 50

    # Dimension 1: Calorie Balance (25%)
    d1 = score_calorie_balance(state.total_kcal, float(state.kcal_target))

    # Dimension 2: Macro Balance (25%)
    d2, macro_balance = score_macro_balance(
        state.total_protein_g, state.total_fat_g, state.total_carbs_g,
        state.total_fiber_g, state.total_kcal,
        target_protein_pct, target_fat_pct, target_carbs_pct,
    )
    state.macro_balance = macro_balance

    # Dimension 3: Food Variety (15%)
    d3 = score_food_variety(state.unique_food_names)

    # Dimension 4: Meal Timing (10%)
    has_breakfast = any(
        m.get("meal_type") == "breakfast" for m in state.parsed_meals
    )
    d4, timing_analysis = score_meal_timing(state.parsed_meals)
    state.meal_timing = timing_analysis

    # Dimension 5: Food Quality (15%)
    d5 = score_food_quality(
        state.processed_food_pct, state.total_sodium_mg,
        state.total_fiber_g, state.total_sugar_g, state.total_kcal,
    )

    # Dimension 6: Programmer Health (10%)
    d6, micro_gaps = score_programmer_health(
        state.total_caffeine_mg, state.total_sodium_mg,
        has_breakfast, state.processed_food_pct,
        state.estimated_lutein_ug, state.estimated_omega3_g,
        state.estimated_vitamin_a_ug, state.estimated_magnesium_mg,
        state.estimated_iron_mg,
    )
    state.micronutrient_gaps = micro_gaps

    # Collect dimensions
    state.dimension_scores = [d1, d2, d3, d4, d5, d6]

    # Composite score
    state.health_score_raw, state.health_grade, score_summary = compute_health_score(
        state.dimension_scores
    )
    state.health_score = state.health_score_raw

    return state


# ============================================================================
# Node 4: Generate Insights (LLM)
# ============================================================================


async def generate_insights(state: NutritionAgentState) -> NutritionAgentState:
    """Use LLM to generate personalized insights, suggestions, and meal ideas."""
    if state.error:
        return state

    start_time = time.perf_counter()

    agent = BaseAgent.get_deep_model()

    system_prompt = """你是一个专业的注册营养师，专门为中国程序员提供饮食分析和建议。

你的任务是基于用户的饮食数据和多维度评分结果，生成：
1. 个性化的饮食综合分析摘要（100-200字，语气温暖共情）
2. 饮食优点（3-5条）
3. 饮食问题和风险（2-4条）
4. 具体可执行的改进建议（3-5条）
5. 明日饮食建议（2-3个具体的餐食创意）

请以 JSON 格式返回分析结果。"""

    user_prompt = f"""## 用户饮食数据

日期：{state.food_record.target_date if state.food_record else 'N/A'}

### 食物列表
{json.dumps([
    {"food": item["food_name"], "kcal": item["energy_kcal"],
     "protein": item["protein_g"], "fat": item["fat_g"], "carbs": item["carbs_g"],
     "fiber": item["fiber_g"], "processed": item.get("is_processed", False)}
    for item in state.all_food_items
], ensure_ascii=False, indent=2)}

### 营养汇总
- 总热量：{state.total_kcal:.0f} kcal（目标 {state.kcal_target} kcal）
- 蛋白质：{state.total_protein_g:.1f}g | 脂肪：{state.total_fat_g:.1f}g | 碳水：{state.total_carbs_g:.1f}g
- 膳食纤维：{state.total_fiber_g:.1f}g | 钠：{state.total_sodium_mg:.0f}mg
- 咖啡因：{state.total_caffeine_mg:.0f}mg
- 食物种类：{state.food_variety_count} 种 | 加工食品占比：{state.processed_food_pct:.0f}%

### 各维度评分
{json.dumps([
    {"维度": d.dimension, "得分": d.score, "等级": d.grade, "详情": d.details, "建议": d.suggestions}
    for d in state.dimension_scores
], ensure_ascii=False, indent=2)}

### 综合健康评分
- 总分：{state.health_score:.1f}/100
- 等级：{state.health_grade}

### 用户画像
{json.dumps({
    "健康目标": state.food_record.user_profile.health_goals if state.food_record and state.food_record.user_profile else [],
    "饮食类型": state.food_record.user_profile.diet_types if state.food_record and state.food_record.user_profile else [],
    "活动水平": state.food_record.user_profile.activity_level if state.food_record and state.food_record.user_profile else "sedentary",
}, ensure_ascii=False)}

请生成综合分析。以 JSON 格式返回：
```json
{{
  "summary": "综合分析摘要",
  "strengths": ["优点1", "优点2", "优点3"],
  "weaknesses": ["问题1", "问题2"],
  "suggestions": ["建议1", "建议2", "建议3", "建议4"],
  "meal_ideas": ["明日餐食创意1", "明日餐食创意2", "明日餐食创意3"]
}}
```
"""

    try:
        response_text = await agent.invoke_llm(system_prompt, user_prompt, response_format="json")
        state.raw_llm_output = response_text
        parsed = agent.parse_json_response(response_text)

        state.ai_summary = parsed.get("summary", "")
        state.ai_strengths = parsed.get("strengths", [])
        state.ai_weaknesses = parsed.get("weaknesses", [])
        state.ai_suggestions = parsed.get("suggestions", [])
        state.ai_meal_ideas = parsed.get("meal_ideas", [])
        state.model_name = agent.model_name

    except Exception as e:
        state.warnings.append(f"LLM insights generation failed: {e}")
        # Fallback: use deterministic summaries
        state.ai_summary = _fallback_summary(state)
        state.ai_strengths = [d.details[0] for d in state.dimension_scores if d.score >= 75][:3]
        state.ai_weaknesses = [d.details[0] for d in state.dimension_scores if d.score < 50][:3]
        state.ai_suggestions = [
            s for d in state.dimension_scores for s in d.suggestions
        ][:5]
        state.ai_meal_ideas = []

    state.analysis_latency_ms = int((time.perf_counter() - start_time) * 1000)

    return state


def _fallback_summary(state: NutritionAgentState) -> str:
    """Generate a deterministic fallback summary when LLM is unavailable."""
    score = state.health_score
    grade = state.health_grade

    if grade in ("A", "B"):
        return (
            f"今日饮食综合评分 {score:.0f}/100（{grade}级），整体表现良好。"
            f"摄入了 {state.food_variety_count} 种食物，热量 {state.total_kcal:.0f} kcal。"
            f"继续保持均衡饮食，注意食物多样化。"
        )
    elif grade == "C":
        return (
            f"今日饮食综合评分 {score:.0f}/100（{grade}级），有改善空间。"
            f"摄入了 {state.food_variety_count} 种食物，热量 {state.total_kcal:.0f} kcal。"
            f"建议关注评分较低的维度，逐步调整饮食结构。"
        )
    else:
        return (
            f"今日饮食综合评分 {score:.0f}/100（{grade}级），需要重视。"
            f"摄入了 {state.food_variety_count} 种食物，热量 {state.total_kcal:.0f} kcal。"
            f"建议从最薄弱的维度开始改善饮食习惯。"
        )


# ============================================================================
# Node 5: Format Output
# ============================================================================


async def format_output(state: NutritionAgentState) -> NutritionAgentState:
    """Assemble the final NutritionAnalysis output object."""
    if state.error:
        return state

    record = state.food_record
    target_date = record.target_date if record else date.today()
    user_id = record.user_id if record else None

    kcal_achievement = round(
        state.total_kcal / state.kcal_target * 100, 1
    ) if state.kcal_target > 0 else 0

    state.final_analysis = NutritionAnalysis(
        target_date=target_date,
        user_id=user_id,
        health_score=state.health_score,
        health_grade=state.health_grade,
        score_summary=(
            f"综合评分 {state.health_score:.0f}/100（{state.health_grade}级）。"
            f"今日摄入 {state.total_kcal:.0f} kcal，{state.food_variety_count} 种食物。"
        ),
        dimensions=state.dimension_scores,
        total_kcal=round(state.total_kcal, 1),
        kcal_target=state.kcal_target,
        kcal_achievement_pct=kcal_achievement,
        macro_balance=state.macro_balance,
        meal_timing=state.meal_timing,
        food_variety_count=state.food_variety_count,
        processed_food_pct=state.processed_food_pct,
        micronutrient_gaps=state.micronutrient_gaps,
        ai_summary=state.ai_summary,
        ai_strengths=state.ai_strengths,
        ai_weaknesses=state.ai_weaknesses,
        ai_suggestions=state.ai_suggestions,
        ai_meal_ideas=state.ai_meal_ideas,
        model_name=state.model_name,
        analysis_latency_ms=state.analysis_latency_ms,
        warnings=state.warnings,
    )

    # Dict output for API
    state.output_dict = state.final_analysis.model_dump()

    return state


# ============================================================================
# Graph Construction
# ============================================================================


def create_nutrition_analysis_graph() -> StateGraph:
    """
    Build the nutrition analysis LangGraph.

    Pipeline:
    ┌──────────┐    ┌────────────┐    ┌───────────┐    ┌────────────┐    ┌──────────┐
    │  parse   │───→│ calculate  │───→│ evaluate  │───→│ generate   │───→│ format   │───→ END
    │  input   │    │ metrics    │    │ scoring   │    │ insights   │    │ output   │
    └──────────┘    └────────────┘    └───────────┘    └────────────┘    └──────────┘
    """

    workflow = StateGraph(NutritionAgentState)

    workflow.add_node("parse_input", parse_input)
    workflow.add_node("calculate_metrics", calculate_metrics)
    workflow.add_node("evaluate_scoring", evaluate_scoring)
    workflow.add_node("generate_insights", generate_insights)
    workflow.add_node("format_output", format_output)

    workflow.set_entry_point("parse_input")
    workflow.add_edge("parse_input", "calculate_metrics")
    workflow.add_edge("calculate_metrics", "evaluate_scoring")
    workflow.add_edge("evaluate_scoring", "generate_insights")
    workflow.add_edge("generate_insights", "format_output")
    workflow.add_edge("format_output", END)

    return workflow.compile()


# Module-level compiled graph
_nutrition_analysis_graph = None

def get_nutrition_analysis_graph():
    global _nutrition_analysis_graph
    if _nutrition_analysis_graph is None:
        _nutrition_analysis_graph = create_nutrition_analysis_graph()
    return _nutrition_analysis_graph

nutrition_analysis_graph = get_nutrition_analysis_graph  # backward compat


# ============================================================================
# Micronutrient Estimation Helpers
# ============================================================================

def _match_food(items: list[dict], keywords: list[str]) -> float:
    """Sum serving_size_g for items matching any keyword."""
    total = 0.0
    for item in items:
        name = item.get("food_name", "").lower()
        if any(kw in name for kw in keywords):
            total += item.get("serving_size_g", 0)
    return total


def _estimate_lutein(items: list[dict]) -> float:
    spinach = _match_food(items, ["菠菜", "羽衣甘蓝", "西兰花", "芥蓝", "南瓜", "玉米", "蛋黄", "鸡蛋"])
    return round(spinach * 30, 0)  # rough μg per gram of lutein-rich foods


def _estimate_omega3(items: list[dict]) -> float:
    fish = _match_food(items, [
        "三文鱼", "沙丁鱼", "金枪鱼", "鲭鱼", "鳕鱼", "秋刀鱼",
        "核桃", "亚麻籽", "奇亚籽", "鱼油",
    ])
    return round(fish * 0.02, 2)  # rough g per gram


def _estimate_vitamin_a(items: list[dict]) -> float:
    sources = _match_food(items, [
        "胡萝卜", "南瓜", "红薯", "菠菜", "西兰花", "蛋黄",
        "动物肝脏", "猪肝", "鸡肝", "芒果", "木瓜",
    ])
    return round(sources * 5, 0)


def _estimate_vitamin_c(items: list[dict]) -> float:
    sources = _match_food(items, [
        "橙", "橘子", "柠檬", "猕猴桃", "草莓", "番茄", "西红柿",
        "青椒", "辣椒", "西兰花", "菠菜", "芒果", "木瓜",
    ])
    return round(sources * 0.5, 1)


def _estimate_calcium(items: list[dict]) -> float:
    sources = _match_food(items, [
        "牛奶", "酸奶", "奶酪", "芝士", "豆腐", "豆干",
        "芝麻", "虾皮", "海带", "紫菜", "西兰花", "杏仁",
    ])
    return round(sources * 1.0, 0)


def _estimate_iron(items: list[dict]) -> float:
    sources = _match_food(items, [
        "牛肉", "羊肉", "猪肝", "鸡肝", "动物肝脏",
        "菠菜", "黑木耳", "红枣", "红豆", "黑豆", "蛤蜊", "牡蛎",
    ])
    return round(sources * 0.03, 1)


def _estimate_magnesium(items: list[dict]) -> float:
    sources = _match_food(items, [
        "杏仁", "核桃", "腰果", "花生", "南瓜籽",
        "菠菜", "牛油果", "香蕉", "黑巧克力", "燕麦", "糙米", "全麦",
    ])
    return round(sources * 0.8, 0)
