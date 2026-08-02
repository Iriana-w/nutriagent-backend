"""
NutriAgent Backend — Middleware.

Request ID injection, request timing, and CORS headers.
"""

from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Inject a unique X-Request-ID header into every response.
    Reads from incoming X-Request-ID or generates a new UUID.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Add X-Process-Time header to every response (milliseconds).
    Logs slow requests (> 1s) at WARNING level.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        import logging

        logger = logging.getLogger("nutriagent")
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Process-Time"] = f"{elapsed_ms:.2f}"

        if elapsed_ms > 1000:
            logger.warning(
                "Slow request: %s %s — %.0fms",
                request.method,
                request.url.path,
                elapsed_ms,
            )

        return response


def register_middleware(app: FastAPI) -> None:
    """Attach all custom middleware to the FastAPI app."""
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(TimingMiddleware)
