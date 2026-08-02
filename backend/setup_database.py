"""
NutriAgent — Database Setup Script

Run: python setup_database.py          (normal — skip existing objects)
Run: python setup_database.py --reset  (drop everything and rebuild)

1. Creates the nutriagent database if it doesn't exist
2. Imports schema.sql (tables, enums, indexes, triggers)
3. Seeds the admin user account
"""

import asyncio
import sys
import os

RESET = "--reset" in sys.argv

sys.path.insert(0, os.path.dirname(__file__))

import asyncpg
import bcrypt

# === Config ===
import os

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "your-db-password")
DB_NAME = os.getenv("DB_NAME", "nutriagent")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@nutriagent.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me")


async def setup():
    # === Step 1: Create database if needed ===
    print("[1/4] Connecting to PostgreSQL...")
    try:
        conn = await asyncpg.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASSWORD,
            database="postgres",
        )
        print("       Connected!")
    except Exception as e:
        print(f"       ERROR: Cannot connect to PostgreSQL: {e}")
        print(f"       Make sure PostgreSQL is running on {DB_HOST}:{DB_PORT}")
        return

    # Check if nutriagent DB exists
    exists = await conn.fetchval(
        "SELECT 1 FROM pg_database WHERE datname = $1", DB_NAME
    )
    if not exists:
        print(f"       Creating database '{DB_NAME}'...")
        await conn.execute(f'CREATE DATABASE "{DB_NAME}"')
        print("       Created!")
    else:
        print(f"       Database '{DB_NAME}' already exists.")
    await conn.close()

    # === Step 2: Import schema ===
    print("[2/4] Importing schema.sql...")
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME,
    )

    if RESET:
        print("       --reset: dropping all tables...")
        await conn.execute(
            "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
        )
        print("       Schema dropped and recreated.")

    schema_path = os.path.join(
        os.path.dirname(__file__), "..", "schema.sql"
    )
    if not os.path.exists(schema_path):
        print(f"       ERROR: schema.sql not found at {schema_path}")
        await conn.close()
        return

    with open(schema_path, encoding="utf-8") as f:
        sql = f.read()

    try:
        await conn.execute(sql)
        print("       Schema imported successfully!")
    except Exception as e:
        print(f"       WARNING (some objects may already exist): {e}")
    await conn.close()

    # === Step 3: Seed admin user ===
    print("[3/4] Seeding admin user...")
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME,
    )

    existing = await conn.fetchval(
        "SELECT id FROM users WHERE email = $1", ADMIN_EMAIL
    )
    if existing:
        print(f"       Admin already exists: {ADMIN_EMAIL}")
    else:
        password_hash = bcrypt.hashpw(
            ADMIN_PASSWORD.encode(), bcrypt.gensalt()
        ).decode()
        await conn.execute(
            "INSERT INTO users (nickname, email, password_hash, is_admin, is_active) "
            "VALUES ($1, $2, $3, $4, $5)",
            "管理员", ADMIN_EMAIL, password_hash, True, True,
        )
        print(f"       Admin created: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")

    await conn.close()

    # === Step 4: Verify ===
    print("[4/4] Verifying...")
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME,
    )
    users = await conn.fetch("SELECT email, nickname, is_admin FROM users")
    tables = await conn.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
    )
    await conn.close()

    print(f"       Users ({len(users)}):")
    for u in users:
        admin_tag = " [ADMIN]" if u["is_admin"] else ""
        print(f"         - {u['email']} ({u['nickname']}){admin_tag}")

    print(f"       Tables ({len(tables)}):")
    for t in tables:
        print(f"         - {t['table_name']}")

    print("\n========================================")
    print("SETUP COMPLETE!")
    print(f"Login: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print("========================================")


if __name__ == "__main__":
    asyncio.run(setup())
