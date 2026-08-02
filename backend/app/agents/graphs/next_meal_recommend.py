"""
NutriAgent Backend — Next Meal Recommendation Graph.

Enhanced LangGraph workflow for personalized next-meal recommendations.
Powered by three core signals: user history, health goals, and budget.

Pipeline (6 nodes):
  analyze_history → align_goals → plan_budget → retrieve_foods → generate → validate

Each node enriches the state with domain-specific analysis before
the final LLM generation produces a structured meal recommendation.
"""

from __future__ import annotations

import json
import time
from datetime import datetime

from langgraph.graph import END, StateGraph

from app.agents.base import BaseAgent
from app.agents.recommendation_state import RecommendationAgentState
from app.config import settings
from app.schemas.recommendation_agent import (
    MealRecommendation,
    NutritionSummary,
    RecommendedItem,
)
from app.tools.budget_planner import budget_planner
from app.tools.food_search import search_foods_by_goal, search_foods_semantic
from app.tools.history_analyzer import history_analyzer
from app.tools.nutrition_kb import format_knowledge_for_prompt


# ============================================================================
# Node 1: Analyze History
# ============================================================================


async def analyze_history(state: RecommendationAgentState) -> RecommendationAgentState:
    """
    Analyze user diet history for patterns, gaps, and repeat avoidance.

    Extracts:
    - Foods to avoid (recent repeats + disliked)
    - Liked foods for preference alignment
    - Eating pattern insights
    - Nutrition gaps from recent history
    """
    req = state.request
    if req is None:
        state.error = "No RecommendationRequest provided"
        return state

    # Compute meal kcal target
    meal_kcal_target = history_analyzer._meal_kcal_target(
        state.meal_type, state.daily_kcal_target
    )

    # Run history analysis
    analysis = history_analyzer.analyze(
        history=req.user_history,
        health_goals=state.health_goals,
        meal_type=state.meal_type,
        daily_kcal_target=state.daily_kcal_target,
    )

    state.avoided_foods = analysis["avoided_foods"]
    state.recent_food_set = set(analysis["avoided_foods"])
    state.meal_pattern_insights = analysis["pattern_insights"]
    state.history_gaps = analysis["gaps"]

    # Store history context for the generator
    state.history = req.user_history

    return state


# ============================================================================
# Node 2: Align Goals
# ============================================================================


async def align_goals(state: RecommendationAgentState) -> RecommendationAgentState:
    """
    Map health goals to specific food requirements and restrictions.

    Each goal type maps to:
    - Required nutrients or food categories
    - Foods to emphasize
    - Foods to avoid
    """
    req = state.request
    goals = req.health_goals if req else []

    if not goals:
        state.goal_context_prompt = "无特定健康目标，按一般均衡饮食推荐。"
        return state

    # Goal-to-food mapping
    GOAL_FOOD_MAP = {
        "lose_weight": {
            "require": ["高蛋白", "低热量密度", "高纤维"],
            "emphasize": ["鸡胸肉", "鱼", "豆腐", "蔬菜", "燕麦", "魔芋"],
            "avoid": ["油炸食品", "甜点", "含糖饮料", "肥肉"],
        },
        "gain_muscle": {
            "require": ["高蛋白", "适量碳水", "优质脂肪"],
            "emphasize": ["牛肉", "鸡胸肉", "鸡蛋", "三文鱼", "牛奶", "豆腐", "糙米"],
            "avoid": ["空热量食物", "酒精"],
        },
        "eye_health": {
            "require": ["叶黄素", "维生素A", "Omega-3", "锌"],
            "emphasize": ["菠菜", "西兰花", "胡萝卜", "蓝莓", "鸡蛋黄", "三文鱼", "南瓜"],
            "avoid": ["高糖食物"],
        },
        "hair_health": {
            "require": ["蛋白质", "铁", "锌", "生物素", "维生素D"],
            "emphasize": ["鸡蛋", "三文鱼", "牛肉", "菠菜", "黑木耳", "坚果", "牡蛎"],
            "avoid": [],
        },
        "blood_sugar": {
            "require": ["低GI", "高纤维", "适量蛋白"],
            "emphasize": ["燕麦", "糙米", "荞麦", "豆类", "蔬菜", "瘦肉"],
            "avoid": ["精制碳水", "甜食", "含糖饮料", "高GI水果"],
        },
        "energy_boost": {
            "require": ["复合碳水", "B族维生素", "铁", "适量咖啡因"],
            "emphasize": ["全谷物", "瘦肉", "鸡蛋", "深绿蔬菜", "香蕉", "坚果"],
            "avoid": ["高糖零食", "过量咖啡"],
        },
        "gut_health": {
            "require": ["膳食纤维", "益生菌", "多酚"],
            "emphasize": ["酸奶", "燕麦", "香蕉", "洋葱", "大蒜", "发酵食品"],
            "avoid": ["过度加工食品", "辛辣刺激（过量）"],
        },
        "anti_inflammatory": {
            "require": ["Omega-3", "多酚", "姜黄素"],
            "emphasize": ["三文鱼", "橄榄油", "姜黄", "蓝莓", "核桃", "绿茶"],
            "avoid": ["油炸食品", "精制碳水", "加工肉制品"],
        },
    }

    state.goal_food_requirements = {}
    all_emphasize = []
    all_avoid = []
    goal_context_lines = []

    for goal in goals:
        mapping = GOAL_FOOD_MAP.get(goal.goal_type, {})
        state.goal_food_requirements[goal.goal_type] = mapping.get("emphasize", [])

        emphasize = mapping.get("emphasize", [])
        avoid = mapping.get("avoid", [])
        require = mapping.get("require", [])

        all_emphasize.extend(emphasize)
        all_avoid.extend(avoid)

        goal_context_lines.append(
            f"**{goal.goal_type}** (优先级 {goal.priority}/10)"
            f"{' — ' + goal.description if goal.description else ''}\n"
            f"  需要：{'、'.join(require)}\n"
            f"  推荐食物：{'、'.join(emphasize[:8])}\n"
            + (f"  应避免：{'、'.join(avoid)}\n" if avoid else "")
        )

    state.goal_avoid_foods = list(set(all_avoid))
    state.goal_context_prompt = (
        "## 🎯 健康目标与食物映射\n\n" + "\n".join(goal_context_lines)
    )

    # Merge goal-avoid with history-avoid for the full avoid list
    merged_avoid = set(state.avoided_foods)
    merged_avoid.update(f.lower() for f in all_avoid)
    state.avoided_foods = list(merged_avoid)

    return state


# ============================================================================
# Node 3: Plan Budget
# ============================================================================


async def plan_budget(state: RecommendationAgentState) -> RecommendationAgentState:
    """
    Determine budget tier, strategy, and price-appropriate food options.
    """
    req = state.request
    budget = req.budget_cent if req else None

    plan = budget_planner.plan(
        budget_cent=budget,
        meal_type=state.meal_type,
        daily_kcal_target=state.daily_kcal_target,
    )

    state.budget_cent_target = plan["budget_cent"]
    state.budget_per_item_max = plan["per_item_max"]
    state.budget_strategy = plan["tier"]
    state.budget_analysis_text = plan["budget_analysis_text"]

    return state


# ============================================================================
# Node 4: Retrieve Foods (RAG)
# ============================================================================


async def retrieve_foods(state: RecommendationAgentState) -> RecommendationAgentState:
    """
    RAG retrieval guided by all three signals: history, goals, and budget.

    1. Nutrition knowledge base lookup (scenario + goals)
    2. Food search by health goals
    3. Semantic food search by meal type + goals
    4. Filter by budget (affordable foods)
    """
    req = state.request
    scenario = req.scenario if req else None
    goal_types = [g.goal_type for g in state.health_goals]

    # --- 1. Knowledge Base ---
    state.retrieved_knowledge = format_knowledge_for_prompt(
        scenario=scenario,
        health_goals=goal_types,
        include_general=True,
    )

    # --- 2. Food search by goals ---
    food_results = []
    state.retrieved_by_goal = {}

    for goal in goal_types:
        try:
            foods = await search_foods_by_goal(goal, limit=5)
            state.retrieved_by_goal[goal] = foods
            food_results.extend(foods)
        except Exception:
            pass

    # --- 3. Semantic food search ---
    query_parts = [state.meal_type]
    for goal in goal_types:
        mapping = {
            "lose_weight": "低卡 高蛋白 高纤维",
            "gain_muscle": "高蛋白 优质碳水",
            "eye_health": "护眼 叶黄素 维生素A",
            "hair_health": "蛋白质 铁 锌",
            "blood_sugar": "低GI 高纤维",
            "energy_boost": "能量 复合碳水 B族",
            "gut_health": "膳食纤维 发酵",
            "anti_inflammatory": "Omega-3 抗炎",
        }
        query_parts.append(mapping.get(goal, ""))

    query = " ".join(p for p in query_parts if p)
    try:
        foods = await search_foods_semantic(query_text=query, limit=10)
        food_results.extend(foods)
    except Exception:
        pass

    # --- 4. Deduplicate ---
    seen = set()
    deduped = []
    for f in food_results:
        fid = f.get("id")
        if fid not in seen:
            seen.add(fid)
            deduped.append(f)
    state.retrieved_foods = deduped[:25]

    # --- 5. Record sources ---
    state.retrieval_sources = {
        "kb_categories": ["general", "programmer_focus"] + ([scenario] if scenario else []),
        "food_count": len(state.retrieved_foods),
        "goals_used": goal_types,
        "budget_tier": state.budget_strategy,
    }

    return state


# ============================================================================
# Node 5: Generate (LLM)
# ============================================================================


async def generate(state: RecommendationAgentState) -> RecommendationAgentState:
    """
    The core LLM generation step.

    Builds a rich prompt incorporating all three signal analyses:
    - History analysis (avoid repeats, leverage likes, address gaps)
    - Health goal alignment (goal-specific food requirements)
    - Budget strategy (price tier, affordable options)

    Then calls the LLM for a structured JSON recommendation.
    """
    start_time = time.perf_counter()
    agent = BaseAgent(model_name=settings.DEEP_LLM_MODEL, temperature=0.7, max_tokens=4096)

    system_prompt = _build_system_prompt(state)
    user_prompt = _build_user_prompt(state)

    state.prompt_text = user_prompt

    try:
        raw_response = await agent.invoke_llm(system_prompt, user_prompt, response_format="json")
        state.raw_llm_output = raw_response
    except Exception as e:
        state.error = f"LLM call failed: {e}"
        return state

    parsed = agent.parse_json_response(raw_response)
    state.structured_output = parsed

    state.summary_text = parsed.get("summary", "")
    state.items = parsed.get("recommendations", parsed.get("items", []))
    state.model_name = agent.model_name
    state.latency_ms = int((time.perf_counter() - start_time) * 1000)

    return state


def _build_system_prompt(state: RecommendationAgentState) -> str:
    """Build the system prompt with all context injected."""
    return f"""你是一个专业的注册营养师和饮食推荐系统，专门为中国程序员群体服务。

## 你的专业知识库
{state.retrieved_knowledge[:2000]}

## 推荐核心原则
1. **历史感知**：基于用户近期饮食历史，避免重复推荐，弥补营养缺口
2. **目标驱动**：每项推荐都要对齐用户的健康目标，并解释为什么
3. **预算友好**：在给定预算内做出最优选择，标注每项食物的大致价格
4. **可执行性**：推荐的餐食用户能方便获取（外卖/食堂/便利店/简单烹饪）
5. **程序员友好**：考虑久坐、用眼过度、咖啡因管理等职业特点

## 输出格式（JSON）
{{
  "summary": "推荐摘要（80-150字，语气温暖口语化，用'你'称呼用户）",
  "history_note": "与近期饮食对比的一句话说明",
  "goal_alignment": "这餐如何支持用户健康目标的解释",
  "budget_note": "预算使用说明",
  "recommendations": [
    {{
      "food_name": "食物名称",
      "serving_size_g": 200,
      "estimated_kcal": 350,
      "estimated_protein_g": 25.0,
      "estimated_fat_g": 12.0,
      "estimated_carbs_g": 40.0,
      "estimated_price_cent": 1500,
      "reason_text": "推荐理由（结合用户健康目标）",
      "nutrition_tags": ["高蛋白", "护眼"],
      "goal_alignment": ["eye_health"],
      "is_budget_friendly": true,
      "alternative": "如果这个不合适，可以选什么替代"
    }}
  ],
  "nutrition_summary": {{
    "total_kcal": 800,
    "total_protein_g": 45.0,
    "total_fat_g": 25.0,
    "total_carbs_g": 95.0,
    "total_fiber_g": 8.0,
    "total_price_cent": 2800,
    "within_budget": true
  }},
  "tips": ["额外饮食建议1", "建议2"],
  "alternatives": [
    {{
      "food_name": "备选方案食物",
      "estimated_kcal": 300,
      "estimated_price_cent": 1000,
      "reason_text": "为什么这是好的备选"
    }}
  ]
}}"""


def _build_user_prompt(state: RecommendationAgentState) -> str:
    """Build the detailed user prompt incorporating all three signals."""
    req = state.request
    parts = []

    # Header
    meal_type_cn = {
        "breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐",
        "snack": "加餐", "late_night": "夜宵",
    }
    parts.append(f"# 请为用户推荐下一餐：{meal_type_cn.get(state.meal_type, state.meal_type)}")

    # --- SIGNAL 1: User Profile ---
    parts.append(f"""
## 👤 用户画像
- 每日热量目标：{state.daily_kcal_target} kcal
- 本餐热量目标：约 {history_analyzer._meal_kcal_target(state.meal_type, state.daily_kcal_target)} kcal
- 宏量素比例：蛋白质{req.target_protein_pct if req else 20}% / 脂肪{req.target_fat_pct if req else 30}% / 碳水{req.target_carbs_pct if req else 50}%
- 活动水平：{req.activity_level if req else 'sedentary'}
- 饮食类型：{', '.join(req.diet_types) if req and req.diet_types else '杂食'}
- 过敏源：{', '.join(req.allergens) if req and req.allergens else '无'}
- 辣度：{req.spice_level if req and req.spice_level is not None else '未设置'}/5
""")

    # --- SIGNAL 2: History Analysis ---
    history_lines = []
    if state.avoided_foods:
        history_lines.append(f"⚠️ **避免推荐**（近3天吃过或不喜欢的）：{', '.join(state.avoided_foods[:15])}")
    if state.meal_pattern_insights:
        history_lines.append("📊 **饮食模式**：")
        history_lines.extend(f"  - {p}" for p in state.meal_pattern_insights)
    if state.history_gaps:
        history_lines.append("🔍 **营养缺口**：")
        history_lines.extend(f"  - {g}" for g in state.history_gaps)
    liked = state.history.liked_foods if state.history else []
    if liked:
        history_lines.append(f"❤️ **用户偏爱**：{', '.join(liked[:10])}")

    if history_lines:
        parts.append("## 📜 饮食历史分析\n" + "\n".join(history_lines))
    else:
        parts.append("## 📜 饮食历史分析\n新用户，暂无历史数据。")

    # --- SIGNAL 3: Health Goals ---
    parts.append(f"""
## 🎯 健康目标
{state.goal_context_prompt if state.goal_context_prompt else '无特定健康目标，均衡饮食即可。'}
""")

    # --- SIGNAL 4: Budget ---
    parts.append(f"""
## 💰 预算分析
{state.budget_analysis_text}
""")

    # --- Context ---
    now = datetime.now()
    parts.append(f"""
## 🕐 当前情境
- 时间：{now.strftime('%H:%M')}
- 季节：{'春' if 3 <= now.month <= 5 else '夏' if 6 <= now.month <= 8 else '秋' if 9 <= now.month <= 11 else '冬'}季
- 工作日/周末：{'周末' if now.weekday() >= 5 else '工作日'}
""")

    # Scenario
    if req and req.scenario:
        parts.append(f"\n## 🏷️ 特殊场景\n{req.scenario}")

    # Delivery constraint
    if req and req.delivery_only:
        parts.append("\n⚠️ **仅推荐可外卖配送的餐食**")

    # Exclude foods
    excludes = list(set((req.exclude_foods if req else []) + state.avoided_foods))
    if excludes:
        parts.append(f"\n## 🚫 强制排除的食物\n{', '.join(excludes[:20])}")

    # Food references
    if state.retrieved_foods:
        food_refs = [
            f"- {f['name_zh']} ({f.get('energy_kcal', '?')}kcal/100g, "
            f"蛋白{f.get('protein_g', '?')}g, 脂肪{f.get('fat_g', '?')}g, 碳水{f.get('carbs_g', '?')}g)"
            for f in state.retrieved_foods[:12]
        ]
        parts.append("## 📚 参考食物库\n" + "\n".join(food_refs))

    # Goal food requirements
    if state.goal_food_requirements:
        goal_foods_lines = []
        for goal, foods in state.goal_food_requirements.items():
            goal_foods_lines.append(f"- **{goal}**：{'、'.join(foods[:6])}")
        parts.append("## 🥗 健康目标推荐食材\n" + "\n".join(goal_foods_lines))

    # Final instruction
    parts.append(f"""
---
请基于以上所有信息，为该用户生成个性化的{meal_type_cn.get(state.meal_type, '餐食')}推荐。
重点考虑：
1. 避免推荐历史中已出现的食物
2. 每项推荐都要解释如何对齐健康目标
3. 标注预估价格并确保在预算内
4. 给出多样化的选择（至少3种不同食物类别）

以 JSON 格式返回。
""")

    return "\n\n".join(parts)


# ============================================================================
# Node 6: Validate
# ============================================================================


async def validate(state: RecommendationAgentState) -> RecommendationAgentState:
    """
    Validate the generated recommendation against all constraints.

    Checks:
    - History: no recent repeats
    - Goals: at least some items align with health goals
    - Budget: total within budget
    - Nutrition: reasonable kcal range for meal type
    - Diversity: at least 3 different food categories represented
    - Safety: no allergens or explicitly excluded foods
    """
    warnings = []
    errors = []

    items = state.items
    if not items:
        errors.append("未生成任何推荐食物")
        state.validation_errors = errors
        state.validation_passed = False
        return state

    # --- 1. History check ---
    if state.avoided_foods:
        for item in items:
            food_name = item.get("food_name", "").lower()
            for avoided in state.avoided_foods:
                if avoided.lower() in food_name or food_name in avoided.lower():
                    warnings.append(f"'{item.get('food_name')}' 最近吃过，建议替换")

    # --- 2. Allergen check ---
    allergens = state.request.allergens if state.request else []
    for item in items:
        food_name = item.get("food_name", "").lower()
        for allergen in allergens:
            if allergen.lower() in food_name:
                errors.append(f"'{item.get('food_name')}' 含有过敏源 '{allergen}'！")

    # --- 3. Goal alignment scoring ---
    total_items = len(items)
    aligned_count = 0
    for item in items:
        item_goals = item.get("goal_alignment", [])
        if item_goals:
            aligned_count += 1
    state.goal_alignment_score = round(
        aligned_count / total_items * 100, 1
    ) if total_items > 0 else 0.0

    if state.goal_alignment_score < 50:
        warnings.append(f"仅 {aligned_count}/{total_items} 项对齐健康目标，建议提高目标关联度")

    # --- 4. Budget check ---
    total_price = sum(
        item.get("estimated_price_cent", 0) or 0 for item in items
    )
    if state.budget_cent_target:
        state.budget_utilization_pct = round(
            total_price / state.budget_cent_target * 100, 1
        )
        if total_price > state.budget_cent_target * 1.2:
            warnings.append(
                f"总价 {total_price/100:.1f}元 超出预算 {state.budget_cent_target/100:.1f}元"
            )
    else:
        state.budget_utilization_pct = None

    # --- 5. Calorie check ---
    total_kcal = sum(item.get("estimated_kcal", 0) or 0 for item in items)
    meal_target = history_analyzer._meal_kcal_target(
        state.meal_type, state.daily_kcal_target
    )
    if total_kcal > meal_target * 1.5:
        warnings.append(f"总热量 {total_kcal:.0f} kcal 偏高（建议约 {meal_target} kcal）")
    elif total_kcal < meal_target * 0.4:
        warnings.append(f"总热量 {total_kcal:.0f} kcal 偏低（建议约 {meal_target} kcal）")

    # --- 6. Diversity check ---
    food_names = [item.get("food_name", "") for item in items]
    diversity_score = min(100, len(set(food_names)) / max(len(food_names), 1) * 100)
    state.diversity_score = round(diversity_score, 1)

    if len(items) < 3:
        warnings.append("推荐食物少于3种，建议增加多样性")

    state.validation_warnings = warnings
    state.validation_errors = errors
    state.validation_passed = len(errors) == 0

    # --- 7. Assemble final output ---
    state.final_recommendation = _assemble_output(state, total_kcal, total_price)

    return state


def _assemble_output(
    state: RecommendationAgentState, total_kcal: float, total_price: int
) -> MealRecommendation:
    """Build the final MealRecommendation from state."""
    structured = state.structured_output

    # Build recommended items
    rec_items = []
    for item_data in state.items:
        rec_items.append(RecommendedItem(
            food_name=item_data.get("food_name", ""),
            serving_size_g=item_data.get("serving_size_g"),
            estimated_kcal=item_data.get("estimated_kcal"),
            estimated_protein_g=item_data.get("estimated_protein_g"),
            estimated_fat_g=item_data.get("estimated_fat_g"),
            estimated_carbs_g=item_data.get("estimated_carbs_g"),
            estimated_price_cent=item_data.get("estimated_price_cent"),
            reason_text=item_data.get("reason_text"),
            nutrition_tags=item_data.get("nutrition_tags", []),
            goal_alignment=item_data.get("goal_alignment", []),
            is_budget_friendly=item_data.get("is_budget_friendly", True),
            alternative=item_data.get("alternative"),
        ))

    # Build alternatives
    alternatives = []
    for alt in structured.get("alternatives", []):
        alternatives.append(RecommendedItem(
            food_name=alt.get("food_name", ""),
            estimated_kcal=alt.get("estimated_kcal"),
            estimated_price_cent=alt.get("estimated_price_cent"),
            reason_text=alt.get("reason_text"),
        ))

    # Nutrition summary
    nut = structured.get("nutrition_summary", {})
    meal_kcal_pct = round(
        total_kcal / state.daily_kcal_target * 100, 1
    ) if state.daily_kcal_target > 0 else None

    nutrition = NutritionSummary(
        total_kcal=nut.get("total_kcal", total_kcal),
        total_protein_g=nut.get("total_protein_g", 0),
        total_fat_g=nut.get("total_fat_g", 0),
        total_carbs_g=nut.get("total_carbs_g", 0),
        total_fiber_g=nut.get("total_fiber_g", 0),
        total_price_cent=nut.get("total_price_cent", total_price),
        within_budget=nut.get("within_budget", True),
        meal_kcal_pct=meal_kcal_pct,
    )

    return MealRecommendation(
        meal_type=state.meal_type,
        generated_at=datetime.utcnow(),
        user_id=state.request.user_id if state.request else None,
        summary_text=state.summary_text,
        items=rec_items,
        nutrition=nutrition,
        goal_alignment_score=state.goal_alignment_score,
        goal_alignment_detail=structured.get("goal_alignment", ""),
        history_awareness=structured.get("history_note", ""),
        diversity_note=f"本餐包含 {len(state.items)} 种食物",
        budget_analysis=structured.get("budget_note", ""),
        budget_utilization_pct=state.budget_utilization_pct,
        tips=structured.get("tips", []),
        alternatives=alternatives,
        model_name=state.model_name,
        analysis_summary={
            "avoided_count": len(state.avoided_foods),
            "goal_alignment_score": state.goal_alignment_score,
            "budget_tier": state.budget_strategy,
            "diversity_score": state.diversity_score,
            "retrieved_foods_count": len(state.retrieved_foods),
        },
        warnings=state.validation_warnings,
    )


# ============================================================================
# Graph Construction
# ============================================================================


def create_next_meal_recommend_graph() -> StateGraph:
    """
    Build the enhanced next-meal recommendation LangGraph.

    ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
    │ analyze  │──→│  align   │──→│  plan    │──→│ retrieve │──→│ generate │──→│ validate │──→ END
    │ history  │   │  goals   │   │ budget   │   │  foods   │   │  (LLM)   │   │          │
    └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘   └────┬─────┘
                                                                                      │
                                                                              ┌───────┴──────┐
                                                                              │ retry if     │
                                                                              │ errors & new │
                                                                              │ error set    │
                                                                              └──────────────┘
    """
    workflow = StateGraph(RecommendationAgentState)

    workflow.add_node("analyze_history", analyze_history)
    workflow.add_node("align_goals", align_goals)
    workflow.add_node("plan_budget", plan_budget)
    workflow.add_node("retrieve_foods", retrieve_foods)
    workflow.add_node("generate", generate)
    workflow.add_node("validate", validate)

    workflow.set_entry_point("analyze_history")
    workflow.add_edge("analyze_history", "align_goals")
    workflow.add_edge("align_goals", "plan_budget")
    workflow.add_edge("plan_budget", "retrieve_foods")
    workflow.add_edge("retrieve_foods", "generate")
    workflow.add_edge("generate", "validate")

    # Conditional retry on validation errors
    workflow.add_conditional_edges(
        "validate",
        _should_retry_generation,
        {"retry": "generate", "end": END},
    )

    return workflow.compile()


def _should_retry_generation(state: RecommendationAgentState) -> str:
    """Retry generation once if there are blocking validation errors."""
    # Never retry if there's a fatal error or no items
    if state.error:
        return "end"
    if state.validation_passed:
        return "end"
    if not state.items:
        return "end"  # LLM didn't produce output, retry won't help
    prev = getattr(state, '_prev_validation_errors', None)
    if state.validation_errors and state.validation_errors != prev:
        object.__setattr__(state, '_prev_validation_errors', list(state.validation_errors))
        return "retry"
    return "end"


# Lazy compiled graph (Vercel-friendly cold start)
_next_meal_recommend_graph = None

def get_next_meal_recommend_graph():
    global _next_meal_recommend_graph
    if _next_meal_recommend_graph is None:
        _next_meal_recommend_graph = create_next_meal_recommend_graph()
    return _next_meal_recommend_graph

next_meal_recommend_graph = get_next_meal_recommend_graph  # backward compat
