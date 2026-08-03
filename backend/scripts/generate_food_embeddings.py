"""
Generate pgvector embeddings for foods that have NULL embedding.

Run: python scripts/generate_food_embeddings.py
Safe to re-run: skips foods that already have embeddings.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncpg
from app.config import settings
from app.tools.embedding import embedding_gen

DB_URL = settings.DATABASE_URL.replace("+asyncpg", "").replace("+psycopg2", "")


async def main():
    conn = await asyncpg.connect(DB_URL, statement_cache_size=0)
    print(f"Connected: ...@{DB_URL.split('@')[-1] if '@' in DB_URL else 'localhost'}")

    # Find foods with null embedding
    rows = await conn.fetch(
        "SELECT id, name_zh, alias, category_id FROM foods WHERE embedding IS NULL"
    )
    total = len(rows)
    print(f"Foods needing embeddings: {total}")

    ok = 0
    fail = 0
    for row in rows:
        emb_text = row["name_zh"]
        if row["alias"] and len(row["alias"]) > 0:
            emb_text += " 别名: " + ", ".join(row["alias"])
        # Add category name
        cat_row = await conn.fetchrow(
            "SELECT name_zh FROM food_categories WHERE id=$1", row["category_id"]
        )
        if cat_row:
            emb_text += f" 类别: {cat_row['name_zh']}"

        try:
            vec = await embedding_gen.embed_text(emb_text)
            emb_str = embedding_gen.embedding_to_pgvector_string(vec)
            await conn.execute(
                "UPDATE foods SET embedding=$1::vector WHERE id=$2",
                emb_str, row["id"],
            )
            ok += 1
        except Exception as e:
            fail += 1
            print(f"  FAIL: {row['name_zh']} — {e}")

    await conn.close()
    print(f"\nDone: {ok} ok, {fail} failed, {total - ok - fail} skipped")


if __name__ == "__main__":
    asyncio.run(main())
