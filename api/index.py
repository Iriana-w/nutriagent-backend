"""
NutriAgent — Vercel Serverless Entry Point.

Vercel auto-detects the FastAPI `app` object and routes HTTP here.
"""

import sys
import os

# Ensure backend/ is on Python path (Vercel runs from project root)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.main import create_app  # noqa: E402

# Create app once per cold start, Vercel caches the instance across warm requests
app = create_app()
