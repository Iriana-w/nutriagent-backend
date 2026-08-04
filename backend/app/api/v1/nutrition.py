"""
NutriAgent Backend — Nutrition Routes.

POST /api/v1/nutrition/analyze         # AI-powered diet analysis (NutritionAgent)
GET  /api/v1/nutrition/dashboard
GET  /api/v1/nutrition/report/weekly
GET  /api/v1/nutrition/report/monthly
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query

from app.agents.nutrition_agent import nutrition_agent
from app.api.deps import CurrentUserId, DBSession
from app.schemas.nutrition import DashboardResponse, WeeklyReportResponse
from app.schemas.nutrition_agent import FoodRecord, NutritionAnalysis
from app.services.nutrition_service import get_daily_dashboard, get_weekly_report

router = APIRouter(prefix="/nutrition", tags=["Nutrition"])


@router.post("/analyze", response_model=NutritionAnalysis, status_code=200)
async def analyze_diet(
    food_record: FoodRecord,
    user_id: CurrentUserId,
) -> NutritionAnalysis:
    """
    Analyze a day's food record using the AI Nutrition Agent.

    The agent evaluates your diet across 6 dimensions:
    1. **热量平衡** (25%) — Calorie intake vs target
    2. **宏量营养素平衡** (25%) — Protein/Fat/Carbs ratio
    3. **食物多样性** (15%) — Unique foods count
    4. **进餐节律** (10%) — Meal timing & distribution
    5. **食物质量** (15%) — Processed food ratio, sodium, fiber
    6. **程序员健康专项** (10%) — Eye health, caffeine, Omega-3

    Returns a comprehensive health score (0-100) with:
    - Per-dimension scores with grades and suggestions
    - Macro balance analysis
    - Meal timing evaluation
    - Micronutrient gap detection
    - AI-generated personalized insights and meal ideas
    """
    # Optionally inject user_id from auth if not provided in the body
    if food_record.user_id is None:
        food_record.user_id = UUID(user_id)

    result = await nutrition_agent.analyze(food_record)
    return result


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    db: DBSession,
    user_id: CurrentUserId,
    target_date: date | None = Query(None, description="Target date (default: today)"),
) -> DashboardResponse:
    """
    Get the nutrition dashboard for a specific date.
    Shows total calories, macros, caffeine, and key micronutrients.
    """
    return await get_daily_dashboard(
        db,
        UUID(user_id),
        target_date or date.today(),
    )


@router.get("/report/weekly", response_model=WeeklyReportResponse)
async def get_weekly_report_route(
    db: DBSession,
    user_id: CurrentUserId,
    week_start: date = Query(..., description="Monday of the target week"),
) -> WeeklyReportResponse:
    """
    Get a weekly nutrition report with AI-generated insights.
    Includes average intake, best/worst days, and improvement suggestions.
    """
    return await get_weekly_report(db, UUID(user_id), week_start)


@router.get("/caffeine")
async def get_caffeine_log(
    db: DBSession,
    user_id: CurrentUserId,
    days: int = Query(7, ge=1, le=30, description="Number of days to look back"),
) -> dict:
    """Get caffeine intake for the last N days."""
    from datetime import date as date_type, timedelta
    from sqlalchemy import text as sa_text

    today = date_type.today()
    start_date = today - timedelta(days=days - 1)

    result = await db.execute(
        sa_text("""
            SELECT log_date, total_mg, drink_count, target_limit_mg, over_limit
            FROM user_caffeine_logs
            WHERE user_id = :uid AND log_date >= :start_date
            ORDER BY log_date DESC
        """),
        {"uid": str(user_id), "start_date": start_date},
    )
    rows = result.fetchall()

    today_row = next((r for r in rows if r.log_date == today), None)
    today_mg = int(today_row.total_mg) if today_row else 0
    limit_mg = int(today_row.target_limit_mg) if today_row else 400
    over_limit = bool(today_row.over_limit) if today_row else False

    daily = []
    for i in range(days):
        d = today - timedelta(days=i)
        row = next((r for r in rows if r.log_date == d), None)
        daily.append({
            "date": d.isoformat(),
            "total_mg": int(row.total_mg) if row else 0,
            "drink_count": int(row.drink_count) if row else 0,
        })
    daily.reverse()

    suggestion = _caffeine_suggestion(today_mg, limit_mg)

    return {
        "today_mg": today_mg,
        "limit_mg": limit_mg,
        "over_limit": over_limit,
        "daily": daily,
        "suggestion": suggestion,
    }


def _caffeine_suggestion(today_mg: int, limit_mg: int) -> str:
    if today_mg > limit_mg:
        return f"今天咖啡因摄入 {today_mg}mg，已超过建议上限 {limit_mg}mg。建议减少咖啡或浓茶，多喝水帮助代谢。"
    if today_mg > limit_mg * 0.75:
        return f"今天咖啡因摄入 {today_mg}mg，接近上限。下午后尽量避免咖啡因摄入，以免影响睡眠。"
    if today_mg > 0:
        return "咖啡因摄入在合理范围内。建议下午2点后不再摄入咖啡因。"
    return "今天还没有咖啡因记录。适量咖啡因（<400mg/天）对提神有益。"


@router.get("/report/monthly", response_model=dict)
async def get_monthly_report(
    db: DBSession,
    user_id: CurrentUserId,
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
) -> dict:
    """
    Get a monthly nutrition summary.
    Aggregates weekly reports for the given month.
    """
    from datetime import date as date_type, timedelta

    # Find the first Monday of the month
    first_day = date_type(year, month, 1)
    # Get all Mondays in the month
    weeks = []
    current = first_day
    while current.month == month:
        if current.weekday() == 0:  # Monday
            weeks.append(current)
        current += timedelta(days=1)

    # Aggregate weekly reports
    weekly_data = []
    for ws in weeks:
        try:
            report = await get_weekly_report(db, UUID(user_id), ws)
            weekly_data.append(report)
        except Exception:
            pass

    return {
        "year": year,
        "month": month,
        "weeks_analyzed": len(weekly_data),
        "reports": [r.model_dump() for r in weekly_data],
    }
