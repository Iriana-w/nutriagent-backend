"""
NutriAgent — Seed Admin User

Run: python seed_admin.py

Creates an initial admin account:
  Email: admin@nutriagent.com
  Password: admin123456
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import bcrypt
from sqlalchemy import text
from app.database import async_session_factory

ADMIN = {
    "nickname": os.getenv("ADMIN_NICKNAME", "管理员"),
    "email": os.getenv("ADMIN_EMAIL", "admin@nutriagent.com"),
    "password": os.getenv("ADMIN_PASSWORD", "change-admin-password"),
    "is_admin": True,
    "is_active": True,
}


async def seed_admin():
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": ADMIN["email"]},
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"[SKIP] Admin already exists: {ADMIN['email']}")
            return

        password_hash = bcrypt.hashpw(
            ADMIN["password"].encode(), bcrypt.gensalt()
        ).decode()

        await session.execute(
            text(
                "INSERT INTO users (nickname, email, password_hash, is_admin, is_active) "
                "VALUES (:nickname, :email, :password_hash, :is_admin, :is_active)"
            ),
            {
                "nickname": ADMIN["nickname"],
                "email": ADMIN["email"],
                "password_hash": password_hash,
                "is_admin": ADMIN["is_admin"],
                "is_active": ADMIN["is_active"],
            },
        )
        await session.commit()
        print(f"[OK] Admin created: {ADMIN['email']} / {ADMIN['password']}")


if __name__ == "__main__":
    asyncio.run(seed_admin())
