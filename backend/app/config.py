"""
NutriAgent Backend — Application Configuration.

All settings are loaded from environment variables with sensible defaults.
Uses pydantic-settings for type-safe configuration management.
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "NutriAgent"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # --- Server ---
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # --- Database ---
    # Supports: local PostgreSQL, Supabase, Railway
    # Set via .env or environment variable (Railway injects DATABASE_URL automatically)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
    DATABASE_SYNC_URL: str = "postgresql://postgres:postgres@localhost:5432/postgres"
    DB_POOL_SIZE: int = 5   # Serverless-friendly default (was 20)
    DB_MAX_OVERFLOW: int = 5  # Serverless-friendly default (was 10)
    DB_ECHO: bool = False

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: str = ""

    # --- JWT ---
    JWT_SECRET_KEY: str = ""  # MUST be set via .env — generate: python -c "import secrets; print(secrets.token_hex(32))"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- LLM / AI ---
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    ANTHROPIC_API_KEY: str = ""
    DEFAULT_LLM_MODEL: str = "deepseek-chat"
    FAST_LLM_MODEL: str = "deepseek-chat"
    DEEP_LLM_MODEL: str = "deepseek-chat"

    # --- CORS ---
    # Supports comma-separated string (Railway/Vercel env var compatible)
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # --- Rate Limiting ---
    RATE_LIMIT_PER_MINUTE: int = 60

    # --- External Services ---
    MEITUAN_API_KEY: str = ""
    ELEME_API_KEY: str = ""

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


# Global singleton — import this everywhere
settings = Settings()
