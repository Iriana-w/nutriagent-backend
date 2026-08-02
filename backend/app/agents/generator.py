"""
NutriAgent Backend — Recommendation Generator Node.

The core LLM generation step. Assembles the final prompt from:
- System prompt template
- User context
- RAG-retrieved knowledge & foods
- Request parameters
Then calls the LLM and parses structured output.
"""

from __future__ import annotations

import json
import time
from datetime import datetime

from app.agents.base import BaseAgent
from app.agents.state import RecommendationState
from app.config import settings


class Generator:
    """LLM-based recommendation generator."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.DEEP_LLM_MODEL
        self.agent = BaseAgent(model_name=self.model_name, temperature=0.7, max_tokens=4096)

    async def generate(self, state: RecommendationState) -> RecommendationState:
        """Generate the recommendation via LLM."""
        start_time = time.perf_counter()

        # Build prompt
        system_prompt = self._build_system_prompt(state)
        user_prompt = self._build_user_prompt(state)

        state.prompt_text = user_prompt

        # Call LLM
        try:
            raw_response = await self.agent.invoke_llm(
                system_prompt, user_prompt, response_format="json"
            )
            state.raw_llm_output = raw_response
        except Exception as e:
            state.error = f"LLM call failed: {e}"
            return state

        # Parse structured output
        parsed = self.agent.parse_json_response(raw_response)
        state.structured_output = parsed

        # Extract fields
        state.summary_text = parsed.get("summary", "")
        state.recommendation_json = parsed
        state.items = parsed.get("recommendations", parsed.get("meals", parsed.get("items", [])))

        # Record metadata
        state.model_name = self.model_name
        state.model_version = parsed.get("model_version")
        state.template_id = parsed.get("template_id")
        state.latency_ms = int((time.perf_counter() - start_time) * 1000)

        return state

    def _build_system_prompt(self, state: RecommendationState) -> str:
        """Build the system prompt with guidelines and context."""
        return f"""你是一个专业的营养师和饮食推荐系统，专注于为中国程序员群体提供个性化饮食建议。

## 你的专业知识
{state.retrieved_knowledge[:3000]}

## 推荐原则
1. 营养均衡：每餐包含优质碳水 + 蛋白质 + 蔬菜/水果
2. 个性化：严格遵循用户健康目标、饮食禁忌和偏好
3. 可执行性：推荐的食物用户能方便获取（外卖/便利店/简单烹饪）
4. 场景适配：根据加班、护眼等特定场景调整推荐重点
5. 多样性：避免与最近饮食记录重复，保证食物多样化
6. 中国本土化：优先推荐中餐和常见亚洲食物

## 输出格式
请以 JSON 格式返回推荐结果，包含以下字段：
- summary: 推荐摘要（给用户看的简短文字，语气友好）
- recommendations: 推荐食物列表，每项包含：
  - item_type: "food" | "dish" | "tip"
  - food_name: 食物名称
  - serving_size_g: 推荐份量（克）
  - estimated_kcal: 预估热量
  - estimated_protein_g: 蛋白质（克）
  - estimated_fat_g: 脂肪（克）
  - estimated_carbs_g: 碳水（克）
  - reason_text: 推荐理由（基于用户健康目标和营养需求的解释）
  - nutrition_tags: 营养亮点标签 ["高蛋白","护眼","低GI"等]
- nutrition_summary: 本餐营养总览
  - total_kcal: 总热量
  - total_protein_g: 总蛋白质
  - total_fat_g: 总脂肪
  - total_carbs_g: 总碳水
- tips: 额外饮食建议（可选）"""

    def _build_user_prompt(self, state: RecommendationState) -> str:
        """Build the structured user prompt."""
        ctx = state.user_context

        parts = []

        # Basic request
        parts.append(f"请为以下用户推荐一餐{state.meal_type}：")

        # User profile summary
        parts.append(f"""
## 用户画像
- 性别：{ctx.get('gender', '未设置')}
- 年龄：{ctx.get('age', '未知')}岁
- BMI：{ctx.get('bmi', '未知')}
- 每日热量目标：{ctx.get('daily_kcal_target', 2000)} kcal
- 宏量营养素比例：蛋白质{ctx.get('target_protein_pct', 20)}% / 脂肪{ctx.get('target_fat_pct', 30)}% / 碳水{ctx.get('target_carbs_pct', 50)}%
- 活动水平：{ctx.get('activity_level', 'sedentary')}
""")

        # Diet preferences
        diet_types = ctx.get("diet_types", [])
        allergens = ctx.get("allergens", [])
        pref_info = []
        if diet_types:
            pref_info.append(f"饮食类型：{', '.join(diet_types)}")
        if allergens:
            pref_info.append(f"过敏/忌口：{', '.join(a['allergen'] + '(' + a['severity'] + ')' for a in allergens)}")
        blacklist = ctx.get("food_blacklist", [])
        if blacklist:
            pref_info.append(f"不喜欢的食物：{', '.join(blacklist)}")
        whitelist = ctx.get("food_whitelist", [])
        if whitelist:
            pref_info.append(f"偏爱的食物：{', '.join(whitelist)}")
        spice = ctx.get("spice_level")
        if spice is not None:
            pref_info.append(f"辣度偏好：{spice}/5")
        budget = ctx.get("budget_per_meal") or state.budget_cent
        if budget:
            pref_info.append(f"每餐预算：{budget / 100 if budget > 100 else budget}元")

        if pref_info:
            parts.append("## 饮食偏好\n" + "\n".join(f"- {p}" for p in pref_info))

        # Health goals
        goals = ctx.get("health_goals", [])
        if goals:
            parts.append("## 健康目标\n" + "\n".join(
                f"- {g['goal']} (优先级: {g['priority']})" for g in goals
            ))

        # Time & environment context
        tc = state.time_context
        if tc:
            parts.append(f"""
## 当前情境
- 时间：{tc.get('current_time', '')}
- 餐次：{tc.get('meal_time_desc', '')}
- 季节：{tc.get('season', '')}
- {tc.get('seasonal_tip', '')}
- {tc.get('work_context', '')}
""")

        # Scenario
        if state.scenario:
            parts.append(f"## 特殊场景：{state.scenario}")

        # Recent meals (avoid repeats)
        recent = ctx.get("recent_meals", [])
        if recent:
            recent_foods = set()
            for meal in recent[:9]:  # last 3 days
                for food in meal.get("foods", []):
                    recent_foods.add(food)
            if recent_foods:
                parts.append(f"## 最近吃过（避免重复）\n{', '.join(list(recent_foods)[:20])}")

        # Exclude list
        if state.exclude_foods:
            parts.append(f"## 必须排除\n{', '.join(state.exclude_foods)}")

        # Retrieved foods for reference
        if state.retrieved_foods:
            food_refs = [
                f"{f['name_zh']} ({f['energy_kcal']:.0f}kcal/100g, "
                f"蛋白{f['protein_g']:.1f}g, 脂肪{f['fat_g']:.1f}g, 碳水{f['carbs_g']:.1f}g)"
                for f in state.retrieved_foods[:10]
            ]
            parts.append("## 参考食物库\n" + "\n".join(f"- {r}" for r in food_refs))

        # Final instruction
        parts.append(f"""
请基于以上信息，为该用户推荐合适的{state.meal_type}。
{"要求：仅推荐可外卖配送的食物" if state.delivery_only else ""}
{"预算限制：不超过" + str(state.budget_cent / 100) + "元" if state.budget_cent else ""}
请以 JSON 格式返回推荐结果。
""")

        return "\n\n".join(parts)
