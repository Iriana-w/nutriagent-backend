"""
NutriAgent Backend — Recommendation Routes.

POST   /api/v1/recommendations/next-meal   # Enhanced: history + goals + budget
POST   /api/v1/recommendations/meal
POST   /api/v1/recommendations/daily
POST   /api/v1/recommendations/weekly
POST   /api/v1/recommendations/scenario
POST   /api/v1/recommendations/{id}/feedback
GET    /api/v1/recommendations             # History
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Path

from app.agents.recommendation_agent import recommendation_agent
from app.api.deps import CurrentUserId, DBSession, Pagination
from app.schemas.common import PaginatedResponse
from app.schemas.recommendation import (
    DailyRecommendRequest,
    FeedbackRequest,
    MealRecommendRequest,
    MealPlanRead,
    RecommendationRead,
    ScenarioRequest,
    WeeklyPlanRequest,
)
from app.schemas.recommendation_agent import MealRecommendation, RecommendationRequest
from app.services.recommendation_service import (
    get_daily_recommendation,
    get_meal_recommendation,
    get_recommendation_history,
    submit_feedback,
)

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.post("/next-meal", response_model=MealRecommendation, status_code=200)
async def recommend_next_meal(
    user_id: CurrentUserId,
    data: RecommendationRequest,
) -> MealRecommendation:
    """
    Generate a personalized next-meal recommendation powered by three signals:

    1. **用户历史 (User History)** — Analyzes recent meals to avoid repeats,
       detect nutrition gaps, and leverage preference signals (likes/dislikes).
    2. **健康目标 (Health Goals)** — Maps active health goals to specific food
       requirements (e.g., eye_health → lutein-rich foods, gain_muscle → high protein).
    3. **预算 (Budget)** — Categorizes into economical/moderate/premium tiers
       and recommends price-appropriate foods.

    The agent runs a 6-node LangGraph pipeline:
    analyze_history → align_goals → plan_budget → retrieve_foods → generate → validate

    Returns:
    - Personalized food recommendations with explainable reasoning
    - Health goal alignment scoring (0-100)
    - Budget utilization analysis
    - History-aware diversity notes
    - Alternative options and tips
    """
    # Inject user_id if not in the request body
    if data.user_id is None:
        data.user_id = UUID(user_id)

    import traceback
    try:
        result = await recommendation_agent.recommend(data)
        return result
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail={
                "error": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc(),
            },
        )


@router.post("/meal", response_model=RecommendationRead, status_code=201)
async def recommend_meal(
    db: DBSession,
    user_id: CurrentUserId,
    data: MealRecommendRequest,
) -> RecommendationRead:
    """
    Generate a single meal recommendation using AI.

    The recommendation engine considers:
    - User health profile, preferences, and goals
    - Time of day and meal type
    - Recent diet history (to avoid repeats)
    - Any specified scenario (overtime, eye_care, etc.)
    - Budget and delivery constraints
    """
    rec = await get_meal_recommendation(
        db,
        UUID(user_id),
        meal_type=data.meal_type,
        scenario=data.scenario,
        budget_cent=data.budget_cent,
        delivery_only=data.delivery_only,
        lat=data.lat,
        lng=data.lng,
        exclude_foods=data.exclude_foods,
    )
    return RecommendationRead.model_validate(rec)


@router.post("/daily", response_model=RecommendationRead, status_code=201)
async def recommend_daily(
    db: DBSession,
    user_id: CurrentUserId,
    data: DailyRecommendRequest,
) -> RecommendationRead:
    """
    Generate a full-day meal plan (breakfast, lunch, dinner + snacks).
    """
    rec = await get_daily_recommendation(
        db,
        UUID(user_id),
        target_date=data.target_date,
        scenario=data.scenario,
        budget_cent=data.budget_cent,
        delivery_only=data.delivery_only,
        lat=data.lat,
        lng=data.lng,
        exclude_foods=data.exclude_foods,
    )
    return RecommendationRead.model_validate(rec)


@router.post("/weekly", response_model=MealPlanRead, status_code=201)
async def recommend_weekly(
    db: DBSession,
    user_id: CurrentUserId,
    data: WeeklyPlanRequest,
) -> MealPlanRead:
    """
    Generate a weekly meal plan. Returns a MealPlan with daily items.
    """
    # Placeholder — full weekly planning is P1
    from app.models.recommendation import MealPlan
    from datetime import date

    plan = MealPlan(
        user_id=UUID(user_id),
        plan_week_start=data.week_start,
        plan_name=f"周食谱 {data.week_start}",
        status="active",
    )
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    return MealPlanRead.model_validate(plan)


@router.post("/scenario", response_model=RecommendationRead, status_code=201)
async def recommend_scenario(
    db: DBSession,
    user_id: CurrentUserId,
    data: ScenarioRequest,
) -> RecommendationRead:
    """
    Generate scenario-based recommendations (e.g., overtime meals,
    eye-care foods, anti-hair-loss diet).
    """
    from app.services.recommendation_service import get_orchestrator
    from app.core.exceptions import RecommendationError

    orchestrator = get_orchestrator()
    try:
        result = await orchestrator.run_scenario_recommendation(
            user_id=user_id,
            scenario=data.scenario,
            meal_type=data.meal_type,
        )
    except Exception as e:
        raise RecommendationError(f"Scenario recommendation failed: {e}")

    from app.models.recommendation import RecommendationLog, RecommendStatusEnum

    rec = RecommendationLog(
        user_id=UUID(user_id),
        recommend_type="scenario",
        scenario=data.scenario,
        meal_type=data.meal_type,
        model_name=result.get("model_name", "unknown"),
        recommendation_json=result.get("recommendation_json", {}),
        summary_text=result.get("summary_text", ""),
        total_tokens=result.get("total_tokens"),
        latency_ms=result.get("latency_ms"),
        status=RecommendStatusEnum.generated,
    )
    db.add(rec)
    await db.flush()
    await db.refresh(rec)
    return RecommendationRead.model_validate(rec)


@router.post("/{recommendation_id}/feedback", response_model=RecommendationRead)
async def submit_recommendation_feedback(
    db: DBSession,
    user_id: CurrentUserId,
    recommendation_id: UUID = Path(..., description="Recommendation ID"),
    data: FeedbackRequest = ...,
) -> RecommendationRead:
    """
    Submit feedback on a recommendation (thumbs up/down, detail text).
    This feedback is used to improve future recommendations via
    agent preference learning.
    """
    rec = await submit_feedback(
        db,
        recommendation_id,
        UUID(user_id),
        feedback=data.feedback,
        detail=data.detail,
        item_feedbacks=data.item_feedbacks,
    )
    return RecommendationRead.model_validate(rec)


@router.get("", response_model=PaginatedResponse[RecommendationRead])
async def list_recommendations(
    db: DBSession,
    user_id: CurrentUserId,
    pagination: Pagination,
) -> PaginatedResponse[RecommendationRead]:
    """
    Get the current user's recommendation history (paginated).
    """
    items, total = await get_recommendation_history(
        db,
        UUID(user_id),
        page=pagination["page"],
        page_size=pagination["page_size"],
    )
    return PaginatedResponse.from_items(
        items=[RecommendationRead.model_validate(r) for r in items],
        total=total,
        page=pagination["page"],
        page_size=pagination["page_size"],
    )
