"""
NutriAgent Backend — Models Package.

Import all models here so they are registered with SQLAlchemy's Base.metadata.
This enables Alembic autogenerate and `Base.metadata.create_all`.
"""

from app.models.agent_memory import (
    AgentMemory,
    AgentMemoryLink,
    AgentPreferenceSignal,
    MemoryTypeEnum,
)
from app.models.chat import ChatMessage, ChatSession, PromptTemplate
from app.models.food import (
    DeliveryDish,
    Food,
    FoodCategory,
    FoodCategoryEnum,
    FoodGoalTag,
)
from app.models.food_log import (
    DailyNutritionSummary,
    FoodLog,
    FoodLogItem,
    MealTypeEnum,
    SourceTypeEnum,
)
from app.models.notification import Notification
from app.models.recommendation import (
    FeedbackEnum,
    MealPlan,
    MealPlanItem,
    RecommendationItem,
    RecommendationLog,
    RecommendStatusEnum,
)
from app.models.user import (
    ActivityLevelEnum,
    DietTypeEnum,
    GenderEnum,
    GoalTypeEnum,
    SeverityEnum,
    User,
    UserAllergen,
    UserCaffeineLog,
    UserDietType,
    UserHealthGoal,
    UserHealthProfile,
    UserPreferences,
)

__all__ = [
    # User domain
    "User",
    "UserHealthProfile",
    "UserDietType",
    "UserHealthGoal",
    "UserAllergen",
    "UserPreferences",
    "UserCaffeineLog",
    # Food domain
    "Food",
    "FoodCategory",
    "FoodGoalTag",
    "DeliveryDish",
    # Food log domain
    "FoodLog",
    "FoodLogItem",
    "DailyNutritionSummary",
    # Recommendation domain
    "RecommendationLog",
    "RecommendationItem",
    "MealPlan",
    "MealPlanItem",
    # Agent memory
    "AgentMemory",
    "AgentMemoryLink",
    "AgentPreferenceSignal",
    # Chat & prompts
    "ChatSession",
    "ChatMessage",
    "PromptTemplate",
    # Notification
    "Notification",
    # Enums
    "GenderEnum",
    "ActivityLevelEnum",
    "DietTypeEnum",
    "GoalTypeEnum",
    "SeverityEnum",
    "MemoryTypeEnum",
    "FoodCategoryEnum",
    "MealTypeEnum",
    "SourceTypeEnum",
    "FeedbackEnum",
    "RecommendStatusEnum",
]
