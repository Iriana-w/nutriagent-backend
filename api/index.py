"""
NutriAgent — Vercel Serverless Entry Point.

This file is the single entry point for Vercel's Python runtime.
Vercel auto-detects the FastAPI app and routes all HTTP requests here.

Cold start: ~2-5s (includes module imports + first DB connection)
Warm requests: Vercel reuses the function instance for subsequent requests.

Usage:
    vercel dev          # Local development with Vercel CLI
    vercel --prod       # Deploy to production
"""

import sys
import os

# Ensure backend/ is on the Python path so 'app.*' imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# Lazy-create the FastAPI app — expensive operations (DB pool, Redis, graph compile)
# are deferred until the first request via lazy initialization.
# Vercel reuses the app instance across warm requests.
_app = None


def get_app():
    global _app
    if _app is None:
        from app.main import create_app
        _app = create_app()
    return _app


# Vercel looks for top-level `app` variable
app = get_app()
