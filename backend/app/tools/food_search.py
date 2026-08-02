"""
NutriAgent Backend — Food Search Tool.

Semantic and keyword-based food search using pgvector for RAG retrieval.
"""

from __future__ import annotations

from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.food import Food, FoodCategory


async def search_foods_semantic(
    query_embedding: list[float] | None = None,
    *,
    query_text: str = "",
    category: str | None = None,
    min_protein: float | None = None,
    max_kcal: float | None = None,
    limit: int = 10,
) -> list[dict]:
    """
    Search foods using pgvector similarity (if embedding provided)
    or fall back to keyword search.
    """
    async with get_session() as db:
        conditions = []

        if category:
            cat_result = await db.execute(
                select(FoodCategory.id).where(FoodCategory.category == category)
            )
            cat_id = cat_result.scalar_one_or_none()
            if cat_id:
                conditions.append(Food.category_id == cat_id)

        if min_protein is not None:
            conditions.append(Food.protein_g >= min_protein)
        if max_kcal is not None:
            conditions.append(Food.energy_kcal <= max_kcal)

        if query_embedding:
            # pgvector cosine similarity search
            embedding_str = f"[{','.join(str(v) for v in query_embedding)}]"
            similarity_expr = text(
                "embedding <=> :emb_vec"
            ).bindparams(emb_vec=embedding_str)

            stmt = (
                select(Food)
                .where(and_(*conditions))
                .order_by(similarity_expr)
                .limit(limit)
            )
        elif query_text:
            # Keyword search via trigram
            conditions.append(Food.name_zh.ilike(f"%{query_text}%"))
            stmt = (
                select(Food)
                .where(and_(*conditions))
                .order_by(Food.is_common.desc(), Food.energy_kcal.asc())
                .limit(limit)
            )
        else:
            # Just return common foods
            stmt = (
                select(Food)
                .where(and_(Food.is_common == True, *conditions))
                .limit(limit)
            )

        result = await db.execute(stmt)
        foods = result.scalars().all()

        return [_food_to_dict(f) for f in foods]


async def search_foods_by_goal(
    goal_type: str,
    *,
    limit: int = 10,
) -> list[dict]:
    """Search foods tagged for a specific health goal."""
    async with get_session() as db:
        stmt = (
            select(Food)
            .join(Food.goal_tags)
            .where(
                and_(
                    text("food_goal_tags.goal_type = :goal"),
                    text("food_goal_tags.relevance > 0.5"),
                )
            )
            .params(goal=goal_type)
            .order_by(text("food_goal_tags.relevance DESC"))
            .limit(limit)
        )
        result = await db.execute(stmt)
        return [_food_to_dict(f) for f in result.scalars().all()]


def _food_to_dict(food: Food) -> dict:
    """Convert a Food ORM object to a dict for agent consumption."""
    return {
        "id": str(food.id),
        "name_zh": food.name_zh,
        "name_en": food.name_en,
        "category_id": food.category_id,
        "energy_kcal": float(food.energy_kcal),
        "protein_g": float(food.protein_g or 0),
        "fat_g": float(food.fat_g or 0),
        "carbs_g": float(food.carbs_g or 0),
        "fiber_g": float(food.fiber_g or 0),
        "sodium_mg": float(food.sodium_mg or 0),
        "cholesterol_mg": float(food.cholesterol_mg or 0),
        "lutein_ug": float(food.lutein_ug) if food.lutein_ug else None,
        "omega3_g": float(food.omega3_g) if food.omega3_g else None,
        "caffeine_mg": float(food.caffeine_mg) if food.caffeine_mg else None,
        "glycemic_index": food.glycemic_index,
        "is_common": food.is_common,
        "is_processed": food.is_processed,
    }
