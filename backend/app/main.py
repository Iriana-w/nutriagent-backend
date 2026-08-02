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

    return app

def _safe_url(url: str) -> str:
    """Mask password in connection URL for safe logging."""
    if "@" in url:
        parts = url.split("@")
        return f"...@{parts[-1]}"
    return url


# ── Direct run ──────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:create_app", host="0.0.0.0", port=8000, reload=True, factory=True)

# ── Local uvicorn: `uvicorn app.main:app` needs top-level `app` ──
elif not _IS_SERVERLESS:
    app = create_app()

# ── Vercel: `api/index.py` calls create_app() — no top-level app needed ──
