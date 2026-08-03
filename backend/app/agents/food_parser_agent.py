"""
NutriAgent Backend — Food Parser Agent.

Parses natural language food descriptions into structured nutrition data.
Uses LLM for extraction + pgvector for food matching.

Pipeline: parse_text → search_foods → calculate_nutrition → assemble
Does NOT modify RecommendationAgent, NutritionAgent, or MemoryAgent.
"""

from __future__ import annotations

import json
import time
from typing import Any

from app.agents.base import BaseAgent
from app.agents.food_parser_state import FoodParserState
from app.schemas.food_log import FoodParseRequest, FoodParseResponse, ParsedFoodItem
from app.tools.food_search import search_foods_semantic


class FoodParserAgent:
    """Natural language food parser with pgvector-backed nutrition lookup."""

    SYSTEM_PROMPT = """你是一个食物解析专家。从用户的中文自然语言中提取食物信息。

## 输出JSON格式
{
  "items": [
    {
      "food_name": "鸡蛋",
      "quantity": 2,
      "unit": "个",
      "estimated_weight_g": 100
    }
  ]
}

## 规则
1. quantity: 数字，如 1, 2, 半
2. unit: 个/杯/碗/盘/份/g/ml/片/块/勺
3. estimated_weight_g: 估算每单位克数
   - 鸡蛋 1个≈50g, 牛奶 1杯≈250ml≈250g
   - 米饭 1碗≈150g, 面包 1片≈30g
   - 肉类 1份≈100g, 蔬菜 1份≈150g
   - 水果 1个≈200g, 坚果 1把≈30g
   - 无法判断时默认 150g
4. serving_size_g = quantity × estimated_weight_g
5. 中文描述如"两个鸡蛋" → quantity=2, unit="个"

只返回JSON，不要其他文字。"""

    def __init__(self):
        self.agent = BaseAgent(model_name=None, temperature=0.1, max_tokens=1024)

    async def parse(self, request: FoodParseRequest) -> FoodParseResponse:
        """Parse natural language into structured food items with nutrition."""
        start = time.perf_counter()
        warnings: list[str] = []

        # ── Node 1: Parse text via LLM ──
        user_msg = f"用户输入：{request.text}"
        if request.meal_type:
            user_msg += f"\n餐次提示：{request.meal_type}"

        parsed_items = []
        try:
            raw = await self.agent.invoke_llm(self.SYSTEM_PROMPT, user_msg)
            result = self.agent.parse_json_response(raw)
            parsed_items = result.get("items", [])
        except Exception as e:
            warnings.append(f"LLM parse failed: {e}")
            return FoodParseResponse(
                original_text=request.text, meal_type=request.meal_type,
                items=[], warnings=warnings, parse_time_ms=int((time.perf_counter() - start) * 1000),
            )

        # ── Node 2: Search foods DB ──
        final_items: list[ParsedFoodItem] = []
        for item in parsed_items:
            food_name = item.get("food_name", "")
            quantity = item.get("quantity")
            unit = item.get("unit", "g")
            est_weight = item.get("estimated_weight_g", 150)

            # Try to find in foods DB
            matched = None
            confidence = 0.3
            try:
                results = await search_foods_semantic(query_text=food_name, limit=3)
                if results:
                    matched = results[0]
                    confidence = 0.85 if matched.get("name_zh") == food_name else 0.6
                else:
                    warnings.append(f"搜索「{food_name}」: 0 结果 (DB中有 {food_name} 吗?)")
            except Exception as e:
                warnings.append(f"搜索「{food_name}」失败: {str(e)[:80]}")

            # Calculate nutrition
            if matched:
                ratio = (est_weight / 100.0) if est_weight > 0 else 1.0
                final_items.append(ParsedFoodItem(
                    food_name=matched["name_zh"],
                    food_id=matched.get("id"),
                    quantity=quantity,
                    unit=unit,
                    serving_size_g=est_weight,
                    energy_kcal=round(float(matched.get("energy_kcal", 0)) * ratio, 1),
                    protein_g=round(float(matched.get("protein_g", 0)) * ratio, 1),
                    fat_g=round(float(matched.get("fat_g", 0)) * ratio, 1),
                    carbs_g=round(float(matched.get("carbs_g", 0)) * ratio, 1),
                    fiber_g=round(float(matched.get("fiber_g", 0)) * ratio, 1),
                    sodium_mg=round(float(matched.get("sodium_mg", 0)) * ratio, 1),
                    confidence=confidence,
                    source="db_match",
                ))
            else:
                # Fallback — no DB match, use LLM estimate
                final_items.append(ParsedFoodItem(
                    food_name=food_name,
                    food_id=None,
                    quantity=quantity,
                    unit=unit,
                    serving_size_g=est_weight,
                    energy_kcal=round(item.get("estimated_kcal", 200), 1),
                    protein_g=round(item.get("estimated_protein_g", 10), 1),
                    fat_g=round(item.get("estimated_fat_g", 8), 1),
                    carbs_g=round(item.get("estimated_carbs_g", 20), 1),
                    fiber_g=0,
                    sodium_mg=0,
                    confidence=0.3,
                    source="ai_estimate",
                ))
                warnings.append(f"未在食物库中找到「{food_name}」，使用AI估算值")

        total_kcal = sum(i.energy_kcal for i in final_items)
        elapsed = int((time.perf_counter() - start) * 1000)

        return FoodParseResponse(
            original_text=request.text,
            meal_type=request.meal_type,
            items=final_items,
            total_kcal=round(total_kcal, 1),
            parse_time_ms=elapsed,
            warnings=warnings,
        )


# Singleton
food_parser_agent = FoodParserAgent()
