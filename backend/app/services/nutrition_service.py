"""
NutriAgent Backend — Nutrition Service.

Handles dashboard aggregation, daily/weekly nutrition analysis.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food_log import DailyNutritionSummary, FoodLog, FoodLogItem
from app.schemas.nutrition import DashboardResponse, MacroBreakdown, WeeklyReportResponse


async def get_daily_dashboard(
    db: AsyncSession,
    user_id: UUID,
    target_date: date,
) -> DashboardResponse:
    """Compute the nutrition dashboard for a specific date."""
    # Aggregate from food_logs for the day
    conditions = [
        FoodLog.user_id == user_id,
        FoodLog.meal_date == target_date,
    ]
    stmt = (
        select(
            func.coalesce(func.sum(FoodLog.total_kcal), 0).label("total_kcal"),
            func.coalesce(func.sum(FoodLog.total_protein_g), 0).label("total_protein_g"),
            func.coalesce(func.sum(FoodLog.total_fat_g), 0).label("total_fat_g"),
            func.coalesce(func.sum(FoodLog.total_carbs_g), 0).label("total_carbs_g"),
            func.coalesce(func.sum(FoodLog.total_fiber_g), 0).label("total_fiber_g"),
            func.coalesce(func.sum(FoodLog.total_sodium_mg), 0).label("total_sodium_mg"),
            func.coalesce(func.sum(FoodLog.total_caffeine_mg), 0).label("total_caffeine_mg"),
            func.count(FoodLog.id).label("meal_count"),
        )
        .where(and_(*conditions))
    )
    result = await db.execute(stmt)
    row = result.one()

    total_kcal = float(row.total_kcal)
    total_protein = float(row.total_protein_g)
    total_fat = float(row.total_fat_g)
    total_carbs = float(row.total_carbs_g)

    # Macro percentages (compute sum in kcal, not grams)
    macro_kcal = total_protein * 4 + total_fat * 9 + total_carbs * 4
    if macro_kcal > 0:
        protein_pct = round(total_protein * 400 / macro_kcal, 1)
        fat_pct = round(total_fat * 900 / macro_kcal, 1)
        carbs_pct = round(total_carbs * 400 / macro_kcal, 1)
    else:
        protein_pct = fat_pct = carbs_pct = 0.0

    # Fetch target kcal from health profile or summary
    kcal_target = None
    existing_summary = await db.execute(
        select(DailyNutritionSummary).where(
            and_(
                DailyNutritionSummary.user_id == user_id,
                DailyNutritionSummary.summary_date == target_date,
            )
        )
    )
    summary = existing_summary.scalar_one_or_none()
    if summary:
        kcal_target = summary.kcal_target or 2000
        nutrition_score = summary.nutrition_score
        score_feedback = summary.score_feedback
    else:
        kcal_target = 2000
        nutrition_score = None
        score_feedback = None

    achievement_pct = round(total_kcal / kcal_target * 100, 1) if kcal_target else None

    return DashboardResponse(
        target_date=target_date,
        total_kcal=total_kcal,
        kcal_target=kcal_target,
        kcal_achievement_pct=achievement_pct,
        macros=MacroBreakdown(
            protein_g=total_protein,
            fat_g=total_fat,
            carbs_g=total_carbs,
            fiber_g=float(row.total_fiber_g),
            protein_pct=protein_pct,
            fat_pct=fat_pct,
            carbs_pct=carbs_pct,
        ),
        meal_count=int(row.meal_count),
        caffeine_mg=float(row.total_caffeine_mg),
        sodium_mg=float(row.total_sodium_mg),
        fiber_g=float(row.total_fiber_g),
        nutrition_score=nutrition_score,
        score_feedback=score_feedback,
    )


async def get_weekly_report(
    db: AsyncSession,
    user_id: UUID,
    week_start: date,
) -> WeeklyReportResponse:
    """
    Generate a weekly nutrition report.
    Aggregates data from daily_nutrition_summary and food_logs.
    """
    week_end = week_start + timedelta(days=6)

    # Fetch daily summaries for the week
    stmt = (
        select(DailyNutritionSummary)
        .where(
            and_(
                DailyNutritionSummary.user_id == user_id,
                DailyNutritionSummary.summary_date >= week_start,
                DailyNutritionSummary.summary_date <= week_end,
            )
        )
        .order_by(DailyNutritionSummary.summary_date)
    )
    result = await db.execute(stmt)
    summaries = list(result.scalars().all())

    if not summaries:
        return WeeklyReportResponse(
            week_start=week_start,
            week_end=week_end,
            ai_summary="暂无本周营养数据。开始记录你的饮食吧！",
            ai_suggestions=["每天记录三餐以获得精准的营养分析"],
        )

    avg_kcal = sum(s.total_kcal for s in summaries) / len(summaries)
    avg_score = (
        sum(s.nutrition_score for s in summaries if s.nutrition_score) / len(summaries)
        if summaries else None
    )
    total_meals = sum(s.meal_count for s in summaries)
    total_kcal_avg_pct = (
        sum(s.kcal_achievement_pct for s in summaries if s.kcal_achievement_pct)
        / len(summaries)
        if summaries
        else None
    )

    # Best & worst days by nutrition score
    scored = [s for s in summaries if s.nutrition_score is not None]
    best_day = max(scored, key=lambda s: s.nutrition_score).summary_date if scored else None
    worst_day = min(scored, key=lambda s: s.nutrition_score).summary_date if scored else None

    return WeeklyReportResponse(
        week_start=week_start,
        week_end=week_end,
        avg_daily_kcal=round(avg_kcal, 1),
        avg_kcal_achievement_pct=round(total_kcal_avg_pct, 1) if total_kcal_avg_pct else None,
        avg_nutrition_score=round(avg_score, 1) if avg_score else None,
        total_meals_logged=total_meals,
        best_day=best_day,
        worst_day=worst_day,
        common_deficiencies=[],
        ai_summary=f"本周平均每日摄入 {avg_kcal:.0f} 千卡，共记录 {total_meals} 餐。",
        ai_suggestions=[
            "保持三餐规律，避免跳过早餐",
            "增加蔬菜和水果的摄入",
            "注意控制外卖的油脂和钠含量",
        ],
        macro_trend={},
    )
