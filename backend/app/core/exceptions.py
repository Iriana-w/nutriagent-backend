"""
NutriAgent Backend — Custom Exceptions & Global Exception Handlers.

All business-logic errors are raised as typed exceptions and caught
by FastAPI exception handlers to produce consistent JSON error responses.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


# --- Base Exception ---
class NutriAgentError(Exception):
    """Base exception for all NutriAgent errors."""

    def __init__(self, message: str, status_code: int = 400, detail: dict | None = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}
        super().__init__(message)


# --- Auth Exceptions ---
class AuthenticationError(NutriAgentError):
    """Raised when authentication fails (wrong password, invalid token, etc.)."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED)


class PermissionDeniedError(NutriAgentError):
    """Raised when an authenticated user lacks permissions."""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)


# --- Resource Exceptions ---
class NotFoundError(NutriAgentError):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str = "Resource", identifier: str | None = None):
        msg = f"{resource} not found"
        if identifier:
            msg = f"{resource} '{identifier}' not found"
        super().__init__(msg, status_code=status.HTTP_404_NOT_FOUND)


class ConflictError(NutriAgentError):
    """Raised when a resource already exists (e.g., duplicate email)."""

    def __init__(self, message: str = "Resource already exists"):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)


class BadRequestError(NutriAgentError):
    """Raised for invalid input that doesn't fit Pydantic validation."""

    def __init__(self, message: str = "Bad request"):
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST)


# --- Service Exceptions ---
class RecommendationError(NutriAgentError):
    """Raised when the AI recommendation engine fails."""

    def __init__(self, message: str = "Failed to generate recommendations"):
        super().__init__(message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RateLimitError(NutriAgentError):
    """Raised when the user exceeds rate limits."""

    def __init__(self, message: str = "Too many requests. Please try again later."):
        super().__init__(message, status_code=status.HTTP_429_TOO_MANY_REQUESTS)


class ExternalServiceError(NutriAgentError):
    """Raised when an external service (外卖 API, LLM API, etc.) fails."""

    def __init__(self, service: str = "External service", message: str = "Service unavailable"):
        super().__init__(
            f"{service}: {message}",
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


# --- Register Exception Handlers ---

def register_exception_handlers(app: FastAPI) -> None:
    """
    Attach global exception handlers to the FastAPI app.
    Called during app startup in main.py.
    """

    @app.exception_handler(NutriAgentError)
    async def nutriagent_error_handler(request: Request, exc: NutriAgentError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.__class__.__name__,
                "message": exc.message,
                "detail": exc.detail,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        # Pass through HTTPException detail (our traceback is there)
        from starlette.exceptions import HTTPException as StarletteHTTPException
        if isinstance(exc, StarletteHTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": type(exc).__name__, "detail": str(exc.detail)},
            )
        import logging
        import traceback

        logger = logging.getLogger("nutriagent")
        logger.exception("Unhandled exception: %s", exc)

        from app.config import settings

        detail = {}
        if settings.DEBUG:
            detail["traceback"] = traceback.format_exc()
            detail["error_type"] = type(exc).__name__
            detail["error_message"] = str(exc)

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred. Please try again later.",
                "detail": detail,
            },
        )
