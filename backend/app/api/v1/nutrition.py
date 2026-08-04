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
from sqlalchemy import select
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


async def _ensure_adaptive_table(db):
    """Create adaptive_nutrition_goals table if not exists."""
    from sqlalchemy import text as sa_text
    await db.execute(sa_text("""
        CREATE TABLE IF NOT EXISTS adaptive_nutrition_goals (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            calorie_target INTEGER,
            protein_target_g FLOAT,
            carb_target_g FLOAT,
            fat_target_g FLOAT,
            reason_text TEXT,
            is_adjusted BOOLEAN DEFAULT false,
            confidence FLOAT DEFAULT 0,
            days_analyzed INTEGER DEFAULT 14,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        )
    """))
    await db.commit()


@router.get("/goals/current")
async def get_adaptive_goals(
    db: DBSession,
    user_id: CurrentUserId,
) -> dict:
    """Get current adaptive nutrition goals (or fallback to profile defaults)."""
    from sqlalchemy import text as sa_text
    from app.models.user import UserHealthProfile

    await _ensure_adaptive_table(db)

    # Check adaptive goals
    result = await db.execute(
        sa_text("""
            SELECT calorie_target, protein_target_g, carb_target_g, fat_target_g,
                   reason_text, is_adjusted, confidence, days_analyzed
            FROM adaptive_nutrition_goals
            WHERE user_id = :uid
            ORDER BY created_at DESC LIMIT 1
        """),
        {"uid": str(user_id)},
    )
    row = result.fetchone()

    if row:
        return {
            "calorie_target": row.calorie_target,
            "protein_target": row.protein_target_g,
            "carb_target": row.carb_target_g,
            "fat_target": row.fat_target_g,
            "is_adjusted": row.is_adjusted,
            "reason": row.reason_text or "",
            "confidence": row.confidence or 0,
            "days_analyzed": row.days_analyzed,
        }

    # Fallback to profile defaults
    profile_result = await db.execute(
        select(UserHealthProfile).where(UserHealthProfile.user_id == UUID(user_id))
    )
    profile = profile_result.scalar_one_or_none()

    kcal = profile.daily_kcal_target if profile else None
    prot_pct = profile.target_protein_pct if profile else 20
    fat_pct = profile.target_fat_pct if profile else 30
    carb_pct = profile.target_carbs_pct if profile else 50

    return {
        "calorie_target": kcal,
        "protein_target": round(kcal * prot_pct / 100 / 4) if kcal else None,
        "carb_target": round(kcal * carb_pct / 100 / 4) if kcal else None,
        "fat_target": round(kcal * fat_pct / 100 / 9) if kcal else None,
        "is_adjusted": False,
        "reason": "",
        "confidence": 0,
        "days_analyzed": 0,
    }


@router.post("/goals/analyze")
async def analyze_and_adjust_goals(
    db: DBSession,
    user_id: CurrentUserId,
) -> dict:
    """Analyze last 14 days and generate adaptive nutrition goals."""
    from datetime import date as date_type, timedelta
    from sqlalchemy import text as sa_text

    await _ensure_adaptive_table(db)

    today = date_type.today()
    start = today - timedelta(days=14)

    # Aggregate food logs for last 14 days
    result = await db.execute(
        sa_text("""
            SELECT
                COALESCE(AVG(daily_kcal), 0) as avg_kcal,
                COALESCE(AVG(daily_protein), 0) as avg_protein,
                COALESCE(AVG(daily_fat), 0) as avg_fat,
                COALESCE(AVG(daily_carbs), 0) as avg_carbs,
                COUNT(*) as days_logged
            FROM (
                SELECT
                    meal_date,
                    SUM(total_kcal) as daily_kcal,
                    SUM(total_protein_g) as daily_protein,
                    SUM(total_fat_g) as daily_fat,
                    SUM(total_carbs_g) as daily_carbs
                FROM food_logs
                WHERE user_id = :uid AND meal_date >= :start_date
                GROUP BY meal_date
            ) sub
        """),
        {"uid": str(user_id), "start_date": start},
    )
    row = result.fetchone()
    avg_kcal = float(row.avg_kcal) if row else 0
    avg_protein = float(row.avg_protein) if row else 0
    avg_fat = float(row.avg_fat) if row else 0
    avg_carbs = float(row.avg_carbs) if row else 0
    days_logged = int(row.days_logged) if row else 0

    if days_logged < 3:
        return {"error": "Not enough data", "days_logged": days_logged, "need": 3}

    # Get user profile targets
    from app.models.user import UserHealthProfile
    profile_result = await db.execute(
        select(UserHealthProfile).where(UserHealthProfile.user_id == UUID(user_id))
    )
    profile = profile_result.scalar_one_or_none()
    kcal_target = profile.daily_kcal_target if profile and profile.daily_kcal_target else 2000
    prot_pct = profile.target_protein_pct if profile else 20
    fat_pct = profile.target_fat_pct if profile else 30
    carb_pct = profile.target_carbs_pct if profile else 50

    target_prot = kcal_target * prot_pct / 100 / 4
    target_fat = kcal_target * fat_pct / 100 / 9
    target_carb = kcal_target * carb_pct / 100 / 4

    # Simple adaptive logic
    kcal_diff_pct = (avg_kcal - kcal_target) / kcal_target * 100 if kcal_target else 0
    prot_diff_pct = (avg_protein - target_prot) / target_prot * 100 if target_prot else 0

    reasons = []
    adj_kcal = kcal_target
    adj_prot = target_prot
    adj_fat = target_fat
    adj_carb = target_carb

    if abs(kcal_diff_pct) > 10:
        adj_kcal = round(kcal_target * (1 - kcal_diff_pct / 200))
        reasons.append(f"过去14天热量{'超标' if kcal_diff_pct > 0 else '不足'}{abs(kcal_diff_pct):.0f}%，建议调整至{adj_kcal}kcal")

    if abs(prot_diff_pct) > 15:
        adj_prot = round(target_prot * (1 + (0 if prot_diff_pct > 0 else 0.2)))
        reasons.append(f"蛋白质摄入{'偏高' if prot_diff_pct > 0 else '不足'}{abs(prot_diff_pct):.0f}%，建议{'减少' if prot_diff_pct > 0 else '增加'}至{adj_prot:.0f}g")

    is_adjusted = len(reasons) > 0
    reason_text = "；".join(reasons) if reasons else "当前摄入与目标一致，无需调整"

    # Upsert adaptive goals
    await db.execute(
        sa_text("""
            INSERT INTO adaptive_nutrition_goals
                (user_id, calorie_target, protein_target_g, carb_target_g, fat_target_g,
                 reason_text, is_adjusted, confidence, days_analyzed, created_at, updated_at)
            VALUES (:uid, :cal, :prot, :carb, :fat, :reason, :adj, :conf, :days, NOW(), NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                calorie_target = EXCLUDED.calorie_target,
                protein_target_g = EXCLUDED.protein_target_g,
                carb_target_g = EXCLUDED.carb_target_g,
                fat_target_g = EXCLUDED.fat_target_g,
                reason_text = EXCLUDED.reason_text,
                is_adjusted = EXCLUDED.is_adjusted,
                confidence = EXCLUDED.confidence,
                days_analyzed = EXCLUDED.days_analyzed,
                updated_at = NOW()
        """),
        {
            "uid": str(user_id), "cal": adj_kcal, "prot": adj_prot,
            "carb": adj_carb, "fat": adj_fat, "reason": reason_text,
            "adj": is_adjusted, "conf": min(0.9, days_logged / 14),
            "days": days_logged,
        },
    )
    await db.commit()

    return {
        "calorie_target": adj_kcal,
        "protein_target": round(adj_prot),
        "carb_target": round(adj_carb),
        "fat_target": round(adj_fat),
        "is_adjusted": is_adjusted,
        "reason": reason_text,
        "confidence": min(0.9, days_logged / 14),
        "days_analyzed": days_logged,
        "avg_intake": {
            "kcal": round(avg_kcal),
            "protein": round(avg_protein),
            "fat": round(avg_fat),
            "carbs": round(avg_carbs),
        },
    }


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
