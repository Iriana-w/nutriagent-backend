"""
NutriAgent Backend — Application Entry Point.

FastAPI application with lifespan management, CORS, middleware registration,
and router mounting.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import register_middleware
from app.database import check_db_health, dispose_engine
from app.redis import close_redis, get_redis

# --- Logging ---
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("nutriagent")


# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & shutdown lifecycle for the FastAPI application."""
    # Startup
    logger.info(
        "%s v%s starting in %s mode",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.ENVIRONMENT,
    )
    try:
        await get_redis()
        logger.info("Redis connected: %s", settings.REDIS_URL)
    except Exception as e:
        logger.warning("Redis not available: %s", e)

    db_ok = await check_db_health()
    if db_ok:
        logger.info("Database connected")
    else:
        logger.warning("Database not reachable — check DATABASE_URL")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await dispose_engine()
    await close_redis()
    logger.info("Shutdown complete.")


# --- Create App ---
app = FastAPI(
    title=f"{settings.APP_NAME} API",
    version=settings.APP_VERSION,
    description="AI-powered health diet recommendation system for programmers",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Custom Middleware ---
register_middleware(app)

# --- Exception Handlers ---
register_exception_handlers(app)

# --- Routers ---
app.include_router(api_v1_router)


# --- Debug / Diagnostics ---
@app.get("/api/v1/debug/llm", tags=["Debug"])
async def debug_llm():
    """Test direct LLM call via httpx."""
    import httpx, traceback
    try:
        async with httpx.AsyncClient(timeout=15.0, trust_env=False) as c:
            r = await c.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": "Bearer sk-5955af8d4a4b40f5aae251eae0273579", "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "messages": [{"role": "user", "content": "say ok"}], "max_tokens": 10},
            )
            return {"status": "ok", "response": r.json()["choices"][0]["message"]["content"]}
    except Exception as e:
        return {"status": "error", "type": type(e).__name__, "message": str(e), "traceback": traceback.format_exc()}


@app.get("/api/v1/debug/db", tags=["Debug"])
async def debug_db():
    """Test raw SQL operations."""
    import traceback
    from app.database import get_session
    try:
        async with get_session() as db:
            from sqlalchemy import text
            # Test 1: chat_messages insert
            sid = await db.execute(text("SELECT id FROM chat_sessions LIMIT 1"))
            sid = sid.scalar_one_or_none()
            if not sid:
                await db.execute(text("INSERT INTO chat_sessions (user_id,session_type) SELECT id,'chat' FROM users LIMIT 1"))
                sid = await db.execute(text("SELECT id FROM chat_sessions LIMIT 1"))
                sid = sid.scalar_one_or_none()
            mid = await db.execute(text("INSERT INTO chat_messages (session_id, role, content) VALUES (:sid, 'user', 'debug test') RETURNING id"), {"sid": sid})
            mid = mid.scalar_one()
            await db.execute(text("DELETE FROM chat_messages WHERE id=:mid"), {"mid": mid})
            # Test 2: agent_memories insert
            uid = await db.execute(text("SELECT id FROM users LIMIT 1"))
            uid = uid.scalar_one()
            mid2 = await db.execute(text("INSERT INTO agent_memories (user_id, memory_type, title, content) VALUES (:uid, 'fact', 'debug', 'test') RETURNING id"), {"uid": uid})
            mid2 = mid2.scalar_one()
            await db.execute(text("DELETE FROM agent_memories WHERE id=:mid"), {"mid": mid2})
            return {"status": "ok", "chat_test": str(mid), "memory_test": str(mid2)}
    except Exception as e:
        return {"status": "error", "type": type(e).__name__, "message": str(e), "traceback": traceback.format_exc()}


# --- Health Check ---
@app.get("/api/v1/health", tags=["System"])
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    db_ok = await check_db_health()
    return {
        "status": "ok" if db_ok else "degraded",
        "version": settings.APP_VERSION,
        "database": "connected" if db_ok else "unavailable",
    }
