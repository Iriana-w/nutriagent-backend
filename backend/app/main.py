"""
NutriAgent Backend — Application Factory.

Supports both traditional (uvicorn) and serverless (Vercel) deployment.

Local:  uvicorn app.main:app --reload
Vercel: api/index.py → create_app()
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import register_middleware
from app.database import check_db_health, dispose_engine, engine
from app.redis import close_redis, get_redis

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("nutriagent")

# Detect runtime mode
_IS_SERVERLESS = bool(os.environ.get("VERCEL_DEPLOYMENT"))


def create_app() -> FastAPI:
    """Create and configure the FastAPI application (used by Vercel + local)."""

    # Lifespan: only for local uvicorn; Vercel handles lifecycle per-request
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("%s v%s starting", settings.APP_NAME, settings.APP_VERSION)
        r = await get_redis()
        logger.info("Redis: %s" % ("connected" if r else "not configured"))
        db_ok = await check_db_health()
        logger.info("Database: %s" % ("connected" if db_ok else "unreachable"))
        yield
        logger.info("Shutting down...")
        await dispose_engine()
        await close_redis()

    app = FastAPI(
        title=f"{settings.APP_NAME} API",
        version=settings.APP_VERSION,
        description="AI-powered health diet recommendation for programmers",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan if not _IS_SERVERLESS else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_middleware(app)
    register_exception_handlers(app)
    app.include_router(api_v1_router)

    @app.get("/api/v1/health", tags=["System"])
    async def health_check():
        import traceback

        result = {
            "status": "ok",
            "version": settings.APP_VERSION,
            "database": "connected",
            "database_url": _safe_url(settings.DATABASE_URL),
        }

        db_ok = await check_db_health()
        if not db_ok:
            # Try once more to get the real error
            try:
                from sqlalchemy import text
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
            except Exception as e:
                result["database_error"] = f"{type(e).__name__}: {e}"
                # Get the root cause
                cause = e
                while getattr(cause, "__cause__", None):
                    cause = cause.__cause__
                result["database_root_error"] = str(cause)[:300]
            result["status"] = "degraded"
            result["database"] = "unavailable"

        return result

    @app.get("/api/v1/debug/db-check", tags=["Debug"])
    async def db_check():
        """Full DB diagnostics."""
        res = {"database_url": _safe_url(settings.DATABASE_URL)}
        try:
            async with engine.connect() as conn:
                from sqlalchemy import text
                r = await conn.execute(text("SELECT version()"))
                res["version"] = r.fetchone()[0][:80]
                r = await conn.execute(text("SELECT extname FROM pg_extension ORDER BY extname"))
                res["extensions"] = [row[0] for row in r.fetchall()]
                r = await conn.execute(text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
                ))
                tables = [row[0] for row in r.fetchall()]
                expected = [
                    "users","user_health_profiles","user_diet_types","user_health_goals",
                    "user_allergens","user_preferences","user_caffeine_logs",
                    "foods","food_categories","food_goal_tags","delivery_dishes",
                    "food_logs","food_log_items","daily_nutrition_summary",
                    "recommendation_logs","recommendation_items","meal_plans","meal_plan_items",
                    "agent_memories","agent_memory_links","agent_preference_signals",
                    "chat_sessions","chat_messages","notifications","prompt_templates",
                ]
                res["missing"] = [t for t in expected if t not in tables]
                res["table_count"] = len(tables)
                res["all_present"] = len(res["missing"]) == 0
                r = await conn.execute(text("SELECT indexname FROM pg_indexes WHERE indexname LIKE '%embedding%'"))
                res["vector_indexes"] = [row[0] for row in r.fetchall()]
                res["status"] = "ok" if res["all_present"] else "incomplete"
        except Exception as e:
            res["status"] = "error"
            res["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        return res

    @app.get("/api/v1/debug/auth-check", tags=["Debug"])
    async def auth_check():
        """Check auth prerequisites."""
        res = {}
        try:
            async with engine.connect() as conn:
                from sqlalchemy import text
                r = await conn.execute(text("SELECT count(*), bool_or(is_admin) FROM users WHERE is_active=true"))
                total, has_admin = r.fetchone()
                res["active_users"] = total
                res["has_admin"] = bool(has_admin)
                r = await conn.execute(text("SELECT email, is_admin, is_active FROM users LIMIT 5"))
                res["sample_users"] = [{"email": row[0], "is_admin": row[1], "is_active": row[2]} for row in r.fetchall()]
        except Exception as e:
            res["db_error"] = str(e)[:200]
        res["jwt_secret_set"] = bool(settings.JWT_SECRET_KEY)
        try:
            from app.redis import get_redis
            r = await get_redis()
            res["redis"] = "connected" if r else "not configured (degraded)"
        except Exception as e:
            res["redis"] = f"error: {e}"
        return res

    return app

def _safe_url(url: str) -> str:


# ── Direct run ──────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:create_app", host="0.0.0.0", port=8000, reload=True, factory=True)

# ── Local uvicorn: `uvicorn app.main:app` needs top-level `app` ──
elif not _IS_SERVERLESS:
    app = create_app()

# ── Vercel: `api/index.py` calls create_app() — no top-level app needed ──
