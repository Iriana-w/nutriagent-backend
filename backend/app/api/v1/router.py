"""
NutriAgent Backend — API v1 Router.

Aggregates all v1 route modules into a single router mounted at /api/v1.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.delivery import router as delivery_router
from app.api.v1.location import router as location_router
from app.api.v1.food_logs import router as food_logs_router
from app.api.v1.memory import router as memory_router
from app.api.v1.nutrition import router as nutrition_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.users import router as users_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(recommendations_router)
api_v1_router.include_router(food_logs_router)
api_v1_router.include_router(delivery_router)
api_v1_router.include_router(nutrition_router)
api_v1_router.include_router(chat_router)
api_v1_router.include_router(memory_router)
api_v1_router.include_router(location_router)
