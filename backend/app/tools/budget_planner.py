"""
NutriAgent Backend — Budget Planner Tool.

Budget-aware food selection for the Recommendation Agent.

Strategies:
- economical: maximize nutrition per yuan, simple foods
- balanced: good quality within budget, moderate variety
- premium: best quality, diverse ingredients (ignores budget soft cap)
"""

from __future__ import annotations


class BudgetPlanner:
    """
    Plans meal recommendations within a budget constraint.

    Budget tiers (per meal, in cents):
    - economical:  < 1500 (<15元) — 食堂/便利店级别
    - moderate:    1500-3500 (15-35元) — 外卖/简餐级别
    - premium:     > 3500 (>35元) — 品质外卖/餐厅级别

    For each tier, suggests appropriate food categories and price ranges.
    """

    # Budget tiers in cents
    TIERS = {
        "economical": (0, 1500),
        "moderate": (1500, 3500),
        "premium": (3500, 999999),
    }

    # Approximate price ranges per food category (in cents, per serving)
    FOOD_PRICE_GUIDE = {
        # Staple foods (主食)
        "米饭": (100, 300),
        "馒头": (50, 200),
        "面条": (800, 2000),
        "全麦面包": (300, 800),
        "燕麦": (200, 500),
        "杂粮饭": (200, 500),
        "红薯": (100, 300),
        "玉米": (200, 400),

        # Proteins
        "鸡蛋": (100, 300),
        "鸡胸肉": (500, 1500),
        "鸡腿": (800, 2000),
        "牛肉": (1500, 4000),
        "猪肉": (800, 2500),
        "三文鱼": (2500, 6000),
        "虾仁": (1200, 3500),
        "豆腐": (300, 800),
        "豆浆": (200, 500),

        # Vegetables
        "清炒时蔬": (500, 1500),
        "凉拌黄瓜": (300, 800),
        "蒜蓉西兰花": (500, 1500),
        "番茄炒蛋": (600, 1500),
        "沙拉": (800, 2500),

        # Fruits
        "苹果": (200, 500),
        "香蕉": (200, 400),
        "蓝莓": (800, 2000),
        "橙子": (200, 500),

        # Dairy
        "牛奶": (300, 800),
        "酸奶": (400, 1000),

        # Snacks
        "坚果": (500, 1500),
        "蛋白棒": (800, 2000),
    }

    # Budget strategy recommendations
    STRATEGIES = {
        "economical": {
            "description": "经济实惠——最大化营养性价比",
            "principles": [
                "优先选择食堂/家庭烹饪类食物",
                "用鸡蛋、豆腐、鸡胸肉替代红肉",
                "当季蔬菜性价比最高",
                "主食选择米饭/馒头等基础碳水",
            ],
            "typical_composition": "1主食 + 1-2蛋白质 + 1蔬菜",
            "max_items": 4,
        },
        "moderate": {
            "description": "均衡品质——在预算内保证营养和口味",
            "principles": [
                "荤素搭配，一荤一素一汤",
                "可以选择口碑好的外卖商家",
                "适当增加水果或奶制品",
                "注意外卖的隐藏成本（包装费、配送费）",
            ],
            "typical_composition": "1主食 + 1荤 + 1素 + 可选汤/饮品",
            "max_items": 5,
        },
        "premium": {
            "description": "品质优先——追求最佳营养和用餐体验",
            "principles": [
                "选择优质蛋白质（深海鱼、牛排等）",
                "多样化蔬菜和超级食物",
                "可以考虑有机/精选食材",
                "注重烹饪方式和摆盘",
            ],
            "typical_composition": "1主食 + 2蛋白质 + 2蔬菜 + 饮品/水果",
            "max_items": 6,
        },
    }

    def plan(self, budget_cent: int | None, meal_type: str, daily_kcal_target: int) -> dict:
        """
        Generate a budget plan for the given constraints.

        Returns:
            dict with: tier, strategy_description, principles, max_items,
                       budget_analysis_text, per_item_max
        """
        if budget_cent is None:
            # Infer from meal type defaults
            budget_cent = self._default_budget(meal_type)

        # Determine tier
        tier = self._classify_tier(budget_cent)
        strategy = self.STRATEGIES[tier]

        # Per-item max (leave room for 3-5 items)
        max_items = strategy["max_items"]
        per_item_max = budget_cent // max_items if max_items > 0 else budget_cent

        # Budget analysis text
        budget_yuan = budget_cent / 100
        analysis_lines = [
            f"💰 本餐预算：{budget_yuan:.0f}元（{tier}档）",
            f"📋 策略：{strategy['description']}",
            f"📊 预计 {max_items} 个单品，单品上限约 {per_item_max / 100:.0f} 元",
        ]
        analysis_lines.append("💡 原则：")
        analysis_lines.extend(f"  - {p}" for p in strategy["principles"])

        # Meal-type specific budget advice
        meal_budget_tips = {
            "breakfast": "早餐建议控制在预算的20-25%，营养密度优先于份量",
            "lunch": "午餐是一天中最重要的一餐，建议分配预算的35-40%",
            "dinner": "晚餐宜清淡，预算的25-30%即可，重点在蔬菜和优质蛋白",
            "snack": "加餐控制在预算内，100-200kcal即可",
            "late_night": "深夜加餐尽量轻食，避免影响睡眠",
        }
        if meal_type in meal_budget_tips:
            analysis_lines.append(f"🕐 {meal_budget_tips[meal_type]}")

        # Price-appropriate food suggestions
        affordable_foods = self._get_affordable_foods(per_item_max)
        analysis_lines.append(f"🍱 预算内推荐食材：{', '.join(affordable_foods[:12])}")

        return {
            "tier": tier,
            "budget_cent": budget_cent,
            "strategy_description": strategy["description"],
            "principles": strategy["principles"],
            "max_items": max_items,
            "per_item_max": per_item_max,
            "typical_composition": strategy["typical_composition"],
            "budget_analysis_text": "\n".join(analysis_lines),
            "affordable_foods": affordable_foods,
        }

    def _classify_tier(self, budget_cent: int) -> str:
        """Classify budget into tier."""
        if budget_cent < 1500:
            return "economical"
        elif budget_cent < 3500:
            return "moderate"
        else:
            return "premium"

    def _default_budget(self, meal_type: str) -> int:
        """Default budget by meal type (in cents)."""
        defaults = {
            "breakfast": 1000,   # 10元
            "lunch": 2500,       # 25元
            "dinner": 2000,      # 20元
            "snack": 800,        # 8元
            "late_night": 1000,  # 10元
        }
        return defaults.get(meal_type, 2000)

    def _get_affordable_foods(self, max_price_cent: int) -> list[str]:
        """Get foods that fit within the per-item budget."""
        affordable = []
        for food, (lo, hi) in self.FOOD_PRICE_GUIDE.items():
            if lo <= max_price_cent:
                affordable.append(food)
        return sorted(affordable, key=lambda f: self.FOOD_PRICE_GUIDE.get(f, (999, 999))[0])


# Singleton
budget_planner = BudgetPlanner()
