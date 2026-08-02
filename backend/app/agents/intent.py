"""
NutriAgent Backend — Intent Classification Node.

Classifies user requests into recommendation types and detects scenario tags.
Uses the fast/cheap LLM model for low-latency classification.
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.agents.state import RecommendationState

INTENT_SYSTEM_PROMPT = """你是一个饮食推荐系统的意图分类器。根据用户请求，输出以下分类结果：

## 请求类型 (request_type)
- meal: 单餐推荐（早餐/午餐/晚餐/加餐/夜宵）
- daily: 一日三餐完整规划
- weekly: 一周食谱计划
- scenario: 特定场景推荐（熬夜/护眼/护发等）

## 餐次 (meal_type)
- breakfast / lunch / dinner / snack / late_night
- 如果用户没有明确指定餐次，根据当前时间推断

## 场景标签 (scenario)
- overtime: 熬夜加班
- eye_care: 护眼
- hair_care: 防脱发
- caffeine_cut: 减少咖啡因
- energy_boost: 提神醒脑
- party_survival: 聚餐生存
- travel: 出差

## 约束条件
- budget: 预算金额（分）
- delivery_only: 是否只要外卖
- exclude_foods: 排除的食物列表

请以 JSON 格式返回分类结果。"""

INTENT_USER_TEMPLATE = """用户请求：{user_message}

当前时间：{current_time}
用户所在餐次（根据时间推断）：{inferred_meal_type}

请分类此请求并返回 JSON。"""


class IntentClassifier:
    """Classifies user requests for routing to the appropriate agent graph."""

    def __init__(self):
        self.agent = BaseAgent.get_fast_model()

    async def classify(self, state: RecommendationState) -> RecommendationState:
        """Classify the intent and update state."""
        from datetime import datetime

        now = datetime.now()
        current_time = now.strftime("%H:%M")
        inferred_meal = self._infer_meal_type(now.hour)

        user_message = self._build_user_message(state)

        prompt = INTENT_USER_TEMPLATE.format(
            user_message=user_message,
            current_time=current_time,
            inferred_meal_type=inferred_meal,
        )

        response = await self.agent.invoke_llm(INTENT_SYSTEM_PROMPT, prompt, response_format="json")
        parsed = self.agent.parse_json_response(response)

        state.intent = parsed.get("request_type", state.request_type)
        state.intent_confidence = parsed.get("confidence", 0.8)
        state.request_type = parsed.get("request_type", state.request_type)
        state.meal_type = parsed.get("meal_type", state.meal_type) or inferred_meal
        state.scenario = parsed.get("scenario", state.scenario)
        state.budget_cent = parsed.get("budget", state.budget_cent)
        state.delivery_only = parsed.get("delivery_only", state.delivery_only)
        state.exclude_foods = parsed.get("exclude_foods", state.exclude_foods)

        return state

    def _build_user_message(self, state: RecommendationState) -> str:
        """Construct a user message from state for intent classification."""
        parts = []
        if state.meal_type:
            parts.append(f"餐次：{state.meal_type}")
        if state.scenario:
            parts.append(f"场景：{state.scenario}")
        if state.budget_cent:
            parts.append(f"预算：{state.budget_cent / 100:.0f}元")
        if state.delivery_only:
            parts.append("只需要外卖推荐")
        if state.exclude_foods:
            parts.append(f"排除食物：{', '.join(state.exclude_foods)}")
        if state.target_date:
            parts.append(f"目标日期：{state.target_date}")

        return "；".join(parts) if parts else f"推荐一餐{state.meal_type or ''}"

    @staticmethod
    def _infer_meal_type(hour: int) -> str:
        """Infer meal type from current hour."""
        if 6 <= hour < 10:
            return "breakfast"
        elif 10 <= hour < 14:
            return "lunch"
        elif 14 <= hour < 18:
            return "snack"
        elif 18 <= hour < 21:
            return "dinner"
        else:
            return "late_night"
