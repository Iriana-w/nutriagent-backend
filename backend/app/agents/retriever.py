"""
NutriAgent Backend — RAG Retrieval Node.

Retrieves relevant nutrition knowledge and food data for the
recommendation engine using:
1. Nutrition knowledge base (static guidelines)
2. pgvector semantic food search
3. Health-goal-tagged food lookup
"""

from __future__ import annotations

from app.agents.state import RecommendationState
from app.tools.food_search import search_foods_by_goal, search_foods_semantic
from app.tools.nutrition_kb import format_knowledge_for_prompt


class Retriever:
    """RAG retriever for the recommendation pipeline."""

    async def retrieve(self, state: RecommendationState) -> RecommendationState:
        """
        Retrieve relevant knowledge and foods based on the request context.
        Runs KB lookup and food searches in parallel.
        """

        # --- 1. Nutrition Knowledge ---
        health_goals = [
            g.get("goal") for g in state.user_context.get("health_goals", [])
        ]
        state.retrieved_knowledge = format_knowledge_for_prompt(
            scenario=state.scenario,
            health_goals=health_goals,
            include_general=True,
        )

        # --- 2. Food Search ---
        food_results = []

        # Search by health goals
        for goal in health_goals:
            try:
                foods = await search_foods_by_goal(goal, limit=5)
                food_results.extend(foods)
            except Exception:
                pass

        # Keyword search based on scenario/meal type
        query = self._build_food_query(state)
        if query:
            try:
                foods = await search_foods_semantic(
                    query_text=query,
                    limit=10,
                )
                food_results.extend(foods)
            except Exception:
                pass

        # Deduplicate by food id
        seen = set()
        deduped = []
        for f in food_results:
            fid = f.get("id")
            if fid not in seen:
                seen.add(fid)
                deduped.append(f)
        state.retrieved_foods = deduped[:20]

        # --- 3. Delivery Search (if applicable) ---
        if state.is_delivery_search:
            try:
                # For delivery, we'd call the delivery service
                # This is a placeholder — in production, integrate with 外卖 API
                state.retrieved_delivery = []
            except Exception:
                state.retrieved_delivery = []

        # --- 4. Record retrieval sources ---
        state.retrieval_sources = {
            "kb_categories": list(set(
                ["general", "programmer_focus"] +
                ([state.scenario] if state.scenario else [])
            )),
            "food_count": len(state.retrieved_foods),
            "delivery_count": len(state.retrieved_delivery),
            "health_goals_used": health_goals,
        }

        return state

    @staticmethod
    def _build_food_query(state: RecommendationState) -> str:
        """Build a food search query from state."""
        parts = []

        if state.meal_type:
            meal_queries = {
                "breakfast": "早餐 主食 蛋白质",
                "lunch": "午餐 主食 肉 蔬菜",
                "dinner": "晚餐 清淡 蔬菜 蛋白质",
                "snack": "零食 水果 坚果 健康",
                "late_night": "夜宵 轻食 低卡",
            }
            parts.append(meal_queries.get(state.meal_type, ""))

        if state.scenario:
            scenario_queries = {
                "overtime": "熬夜 低GI 蛋白质 提神",
                "eye_care": "护眼 叶黄素 维生素A 胡萝卜",
                "hair_care": "防脱发 蛋白质 铁 锌 生物素",
                "caffeine_cut": "无咖啡因 替代饮品",
                "energy_boost": "能量 复合碳水 铁 B族维生素",
            }
            parts.append(scenario_queries.get(state.scenario, ""))

        return " ".join(p for p in parts if p)
