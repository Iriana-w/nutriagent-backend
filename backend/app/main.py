"""
NutriAgent Backend — Application Factory.

Supports both traditional (uvicorn) and serverless (Vercel) deployment.

Local:  uvicorn app.main:app --reload
Vercel: api/index.py → create_app()
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import register_middleware
from app.database import check_db_health, dispose_engine, engine
from app.redis import close_redis, get_redis

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("nutriagent")

# Detect runtime mode
_IS_SERVERLESS = bool(os.environ.get("VERCEL_DEPLOYMENT"))


def create_app() -> FastAPI:
    """Create and configure the FastAPI application (used by Vercel + local)."""

    # Lifespan: only for local uvicorn; Vercel handles lifecycle per-request
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("%s v%s starting", settings.APP_NAME, settings.APP_VERSION)
        r = await get_redis()
        logger.info("Redis: %s" % ("connected" if r else "not configured"))
        db_ok = await check_db_health()
        logger.info("Database: %s" % ("connected" if db_ok else "unreachable"))
        yield
        logger.info("Shutting down...")
        await dispose_engine()
        await close_redis()

    app = FastAPI(
        title=f"{settings.APP_NAME} API",
        version=settings.APP_VERSION,
        description="AI-powered health diet recommendation for programmers",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan if not _IS_SERVERLESS else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_middleware(app)
    register_exception_handlers(app)
    app.include_router(api_v1_router)

    @app.get("/api/v1/health", tags=["System"])
    async def health_check():
        import traceback

        result = {
            "status": "ok",
            "version": settings.APP_VERSION,
            "database": "connected",
            "database_url": _safe_url(settings.DATABASE_URL),
        }

        db_ok = await check_db_health()
        if not db_ok:
            # Try once more to get the real error
            try:
                from sqlalchemy import text
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
            except Exception as e:
                result["database_error"] = f"{type(e).__name__}: {e}"
                # Get the root cause
                cause = e
                while getattr(cause, "__cause__", None):
                    cause = cause.__cause__
                result["database_root_error"] = str(cause)[:300]
            result["status"] = "degraded"
            result["database"] = "unavailable"

        return result

    @app.get("/api/v1/debug/db-check", tags=["Debug"])
    async def db_check():
        """Full DB diagnostics."""
        res = {"database_url": _safe_url(settings.DATABASE_URL)}
        try:
            async with engine.connect() as conn:
                from sqlalchemy import text
                r = await conn.execute(text("SELECT version()"))
                res["version"] = r.fetchone()[0][:80]
                r = await conn.execute(text("SELECT extname FROM pg_extension ORDER BY extname"))
                res["extensions"] = [row[0] for row in r.fetchall()]
                r = await conn.execute(text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
                ))
                tables = [row[0] for row in r.fetchall()]
                expected = [
                    "users","user_health_profiles","user_diet_types","user_health_goals",
                    "user_allergens","user_preferences","user_caffeine_logs",
                    "foods","food_categories","food_goal_tags","delivery_dishes",
                    "food_logs","food_log_items","daily_nutrition_summary",
                    "recommendation_logs","recommendation_items","meal_plans","meal_plan_items",
                    "agent_memories","agent_memory_links","agent_preference_signals",
                    "chat_sessions","chat_messages","notifications","prompt_templates",
                ]
                res["missing"] = [t for t in expected if t not in tables]
                res["table_count"] = len(tables)
                res["all_present"] = len(res["missing"]) == 0
                r = await conn.execute(text("SELECT indexname FROM pg_indexes WHERE indexname LIKE '%embedding%'"))
                res["vector_indexes"] = [row[0] for row in r.fetchall()]
                res["status"] = "ok" if res["all_present"] else "incomplete"
        except Exception as e:
            res["status"] = "error"
            res["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        return res

    @app.get("/api/v1/debug/auth-check", tags=["Debug"])
    async def auth_check():
        """Check auth prerequisites."""
        res = {}
        try:
            async with engine.connect() as conn:
                from sqlalchemy import text
                r = await conn.execute(text("SELECT count(*), bool_or(is_admin) FROM users WHERE is_active=true"))
                total, has_admin = r.fetchone()
                res["active_users"] = total
                res["has_admin"] = bool(has_admin)
                r = await conn.execute(text("SELECT email, is_admin, is_active FROM users LIMIT 5"))
                res["sample_users"] = [{"email": row[0], "is_admin": row[1], "is_active": row[2]} for row in r.fetchall()]
        except Exception as e:
            res["db_error"] = str(e)[:200]
        res["jwt_secret_set"] = bool(settings.JWT_SECRET_KEY)
        try:
            from app.redis import get_redis
            r = await get_redis()
            res["redis"] = "connected" if r else "not configured (degraded)"
        except Exception as e:
            res["redis"] = f"error: {e}"
        return res

    @app.post("/api/v1/debug/seed-foods", tags=["Debug"])
    async def seed_foods_endpoint():
        """Run food seed data import (one-time setup)."""
        import traceback
        result = {"status": "running"}
        try:
            async with engine.connect() as conn:
                from sqlalchemy import text as sa_text
                # Add unique constraint
                try:
                    await conn.execute(sa_text("ALTER TABLE foods ADD CONSTRAINT foods_name_zh_key UNIQUE (name_zh)"))
                    await conn.commit()
                    result["constraint"] = "added"
                except Exception:
                    result["constraint"] = "already exists or skipped"

                # Insert seed data
                from app.tools.embedding import embedding_gen

                SEED = [
                    {"n":"白米饭","e":"Steamed Rice","a":["米饭","大米饭"],"c":"staple","kcal":116,"p":2.6,"f":0.3,"cb":25.6,"fb":0.3,"sug":0.1,"na":2},
                    {"n":"馒头","e":"Steamed Bun","a":["馍馍","白面馒头"],"c":"staple","kcal":223,"p":7.0,"f":1.1,"cb":44.2,"fb":1.3,"sug":2.0,"na":165},
                    {"n":"面条","e":"Noodles","a":["挂面","切面","白面条"],"c":"staple","kcal":284,"p":8.3,"f":0.7,"cb":61.9,"fb":1.7,"sug":1.0,"na":2},
                    {"n":"燕麦","e":"Oats","a":["燕麦片","燕麦粥"],"c":"staple","kcal":377,"p":13.5,"f":6.7,"cb":61.6,"fb":10.6,"sug":0.9,"na":2},
                    {"n":"全麦面包","e":"Whole Wheat Bread","a":["全麦吐司","黑面包"],"c":"staple","kcal":247,"p":13.0,"f":3.4,"cb":41.3,"fb":7.0,"sug":4.0,"na":400},
                    {"n":"红薯","e":"Sweet Potato","a":["地瓜","番薯","甘薯"],"c":"staple","kcal":86,"p":1.6,"f":0.1,"cb":20.1,"fb":3.0,"sug":4.2,"na":55},
                    {"n":"玉米","e":"Corn","a":["玉米棒","苞米"],"c":"staple","kcal":112,"p":4.0,"f":1.2,"cb":22.8,"fb":2.8,"sug":3.2,"na":2},
                    {"n":"小米粥","e":"Millet Porridge","a":["小米","黄米粥"],"c":"staple","kcal":46,"p":1.4,"f":0.7,"cb":8.4,"fb":0.7,"sug":0.1,"na":2},
                    {"n":"猪肉","e":"Pork","a":["瘦肉","猪瘦肉"],"c":"meat","kcal":143,"p":20.3,"f":6.2,"cb":1.5,"fb":0,"sug":0,"na":57},
                    {"n":"牛肉","e":"Beef","a":["牛瘦肉","牛里脊"],"c":"meat","kcal":125,"p":19.9,"f":4.2,"cb":2.0,"fb":0,"sug":0,"na":84},
                    {"n":"羊肉","e":"Lamb","a":["羊瘦肉","羊腿肉"],"c":"meat","kcal":203,"p":19.0,"f":14.1,"cb":0,"fb":0,"sug":0,"na":80},
                    {"n":"鸡胸肉","e":"Chicken Breast","a":["鸡脯肉","鸡肉","鸡大胸"],"c":"poultry","kcal":133,"p":31.0,"f":1.2,"cb":0,"fb":0,"sug":0,"na":45},
                    {"n":"鸡腿","e":"Chicken Leg","a":["鸡腿肉","琵琶腿"],"c":"poultry","kcal":181,"p":16.0,"f":13.0,"cb":0,"fb":0,"sug":0,"na":60},
                    {"n":"鸭肉","e":"Duck","a":["鸭胸肉"],"c":"poultry","kcal":240,"p":15.5,"f":19.7,"cb":0.2,"fb":0,"sug":0,"na":70},
                    {"n":"猪排骨","e":"Pork Ribs","a":["排骨","猪小排"],"c":"meat","kcal":264,"p":18.3,"f":20.4,"cb":1.7,"fb":0,"sug":0,"na":62},
                    {"n":"三文鱼","e":"Salmon","a":["鲑鱼","大马哈鱼"],"c":"seafood","kcal":208,"p":20.4,"f":13.4,"cb":0,"fb":0,"sug":0,"na":59},
                    {"n":"虾仁","e":"Shrimp","a":["虾","大虾","对虾","基围虾"],"c":"seafood","kcal":99,"p":20.3,"f":0.7,"cb":0.2,"fb":0,"sug":0,"na":150},
                    {"n":"带鱼","e":"Hairtail","a":["刀鱼","白带鱼"],"c":"seafood","kcal":127,"p":17.7,"f":4.9,"cb":3.1,"fb":0,"sug":0,"na":110},
                    {"n":"金枪鱼","e":"Tuna","a":["吞拿鱼","鲔鱼"],"c":"seafood","kcal":144,"p":23.3,"f":4.9,"cb":0,"fb":0,"sug":0,"na":39},
                    {"n":"鲈鱼","e":"Sea Bass","a":["花鲈"],"c":"seafood","kcal":105,"p":18.6,"f":3.4,"cb":0,"fb":0,"sug":0,"na":80},
                    {"n":"鸡蛋","e":"Egg","a":["鸡蛋黄","煮鸡蛋","炒鸡蛋","蛋"],"c":"egg","kcal":144,"p":13.3,"f":8.8,"cb":2.8,"fb":0,"sug":0.5,"na":131},
                    {"n":"牛奶","e":"Milk","a":["鲜奶","全脂牛奶","纯牛奶"],"c":"dairy","kcal":54,"p":3.0,"f":3.2,"cb":3.4,"fb":0,"sug":3.4,"na":41},
                    {"n":"酸奶","e":"Yogurt","a":["酸牛奶","优格"],"c":"dairy","kcal":72,"p":2.5,"f":2.7,"cb":9.3,"fb":0,"sug":9.3,"na":40},
                    {"n":"豆浆","e":"Soy Milk","a":["豆奶","现磨豆浆"],"c":"dairy","kcal":31,"p":3.0,"f":1.6,"cb":1.2,"fb":1.2,"sug":0.5,"na":2},
                    {"n":"豆腐","e":"Tofu","a":["嫩豆腐","老豆腐","北豆腐"],"c":"legume","kcal":81,"p":8.1,"f":3.7,"cb":4.2,"fb":0.4,"sug":0.5,"na":7},
                    {"n":"番茄","e":"Tomato","a":["西红柿"],"c":"vegetable","kcal":20,"p":0.9,"f":0.2,"cb":3.5,"fb":1.2,"sug":2.6,"na":5},
                    {"n":"黄瓜","e":"Cucumber","a":["青瓜","胡瓜"],"c":"vegetable","kcal":16,"p":0.7,"f":0.1,"cb":2.9,"fb":0.5,"sug":1.6,"na":2},
                    {"n":"白菜","e":"Chinese Cabbage","a":["大白菜","小白菜","娃娃菜"],"c":"vegetable","kcal":13,"p":1.5,"f":0.2,"cb":2.2,"fb":0.8,"sug":1.0,"na":8},
                    {"n":"菠菜","e":"Spinach","a":["赤根菜"],"c":"vegetable","kcal":28,"p":2.6,"f":0.3,"cb":4.5,"fb":2.2,"sug":0.4,"na":85},
                    {"n":"西兰花","e":"Broccoli","a":["花椰菜","青花菜"],"c":"vegetable","kcal":36,"p":4.1,"f":0.6,"cb":4.3,"fb":1.6,"sug":1.7,"na":27},
                    {"n":"胡萝卜","e":"Carrot","a":["红萝卜"],"c":"vegetable","kcal":37,"p":1.0,"f":0.2,"cb":8.8,"fb":2.8,"sug":4.7,"na":71},
                    {"n":"生菜","e":"Lettuce","a":["叶生菜","球生菜"],"c":"vegetable","kcal":13,"p":1.3,"f":0.3,"cb":1.3,"fb":1.3,"sug":0.6,"na":25},
                    {"n":"土豆","e":"Potato","a":["马铃薯","洋芋","薯仔"],"c":"vegetable","kcal":81,"p":2.0,"f":0.2,"cb":17.5,"fb":2.1,"sug":0.8,"na":6},
                    {"n":"茄子","e":"Eggplant","a":["矮瓜","落苏"],"c":"vegetable","kcal":21,"p":1.1,"f":0.2,"cb":4.9,"fb":1.3,"sug":2.4,"na":2},
                    {"n":"青椒","e":"Green Pepper","a":["甜椒","柿子椒","灯笼椒"],"c":"vegetable","kcal":22,"p":1.0,"f":0.2,"cb":4.6,"fb":1.7,"sug":2.4,"na":3},
                    {"n":"苹果","e":"Apple","a":["红富士","嘎啦苹果"],"c":"fruit","kcal":53,"p":0.3,"f":0.2,"cb":13.8,"fb":2.4,"sug":10.4,"na":1},
                    {"n":"香蕉","e":"Banana","a":["大蕉","芭蕉"],"c":"fruit","kcal":93,"p":1.1,"f":0.2,"cb":22.8,"fb":2.6,"sug":12.2,"na":1},
                    {"n":"橙子","e":"Orange","a":["甜橙","脐橙"],"c":"fruit","kcal":48,"p":0.9,"f":0.1,"cb":11.8,"fb":2.4,"sug":9.4,"na":1},
                    {"n":"西瓜","e":"Watermelon","a":[],"c":"fruit","kcal":31,"p":0.6,"f":0.1,"cb":7.6,"fb":0.4,"sug":6.2,"na":1},
                    {"n":"葡萄","e":"Grape","a":["提子","红提"],"c":"fruit","kcal":44,"p":0.5,"f":0.2,"cb":10.3,"fb":0.9,"sug":8.5,"na":2},
                    {"n":"草莓","e":"Strawberry","a":["士多啤梨","红莓"],"c":"fruit","kcal":32,"p":0.7,"f":0.3,"cb":7.7,"fb":2.0,"sug":4.9,"na":1},
                    {"n":"蓝莓","e":"Blueberry","a":["越橘"],"c":"fruit","kcal":57,"p":0.7,"f":0.3,"cb":14.5,"fb":2.4,"sug":10.0,"na":1},
                    {"n":"猕猴桃","e":"Kiwi","a":["奇异果"],"c":"fruit","kcal":61,"p":1.1,"f":0.5,"cb":14.7,"fb":3.0,"sug":9.0,"na":3},
                    {"n":"核桃","e":"Walnut","a":["胡桃","核桃仁"],"c":"nut","kcal":646,"p":14.9,"f":58.8,"cb":19.1,"fb":9.5,"sug":2.6,"na":2},
                    {"n":"花生","e":"Peanut","a":["花生米","落花生"],"c":"nut","kcal":567,"p":25.8,"f":49.2,"cb":16.1,"fb":8.5,"sug":4.7,"na":18},
                    {"n":"杏仁","e":"Almond","a":["巴旦木","扁桃仁"],"c":"nut","kcal":578,"p":21.2,"f":49.9,"cb":21.6,"fb":12.5,"sug":4.4,"na":1},
                    {"n":"咖啡","e":"Coffee","a":["美式","黑咖啡","清咖"],"c":"beverage","kcal":2,"p":0.1,"f":0,"cb":0,"fb":0,"sug":0,"na":2},
                    {"n":"绿茶","e":"Green Tea","a":["茶","龙井","碧螺春"],"c":"beverage","kcal":1,"p":0,"f":0,"cb":0.2,"fb":0,"sug":0,"na":1},
                    {"n":"可乐","e":"Cola","a":["可口可乐","百事可乐","汽水"],"c":"beverage","kcal":42,"p":0,"f":0,"cb":10.6,"fb":0,"sug":10.6,"na":4},
                    {"n":"酱油","e":"Soy Sauce","a":["生抽","老抽","豉油"],"c":"condiment","kcal":63,"p":5.6,"f":0.1,"cb":10.1,"fb":0,"sug":1.5,"na":5757},
                    {"n":"食用油","e":"Cooking Oil","a":["花生油","菜籽油","大豆油","色拉油"],"c":"oil","kcal":899,"p":0,"f":99.9,"cb":0,"fb":0,"sug":0,"na":0},
                    {"n":"盐","e":"Salt","a":["食盐","海盐","精盐"],"c":"condiment","kcal":0,"p":0,"f":0,"cb":0,"fb":0,"sug":0,"na":38758},
                ]

                # Get category IDs
                cat_rows = await conn.execute(sa_text("SELECT category, id FROM food_categories"))
                cat_map = {row[0]: row[1] for row in cat_rows.fetchall()}

                added = 0
                skipped = 0
                for f in SEED:
                    cid = cat_map.get(f["c"])
                    if not cid: continue
                    emb_text = f["n"]
                    if f.get("a"): emb_text += " 别名: " + ", ".join(f["a"])
                    emb_text += f" 类别: {f['c']}"
                    try:
                        vec = await embedding_gen.embed_text(emb_text)
                        emb_str = embedding_gen.embedding_to_pgvector_string(vec)
                    except Exception:
                        emb_str = None

                    try:
                        await conn.execute(
                            sa_text("""INSERT INTO foods (name_zh,name_en,alias,category_id,energy_kcal,protein_g,fat_g,carbs_g,fiber_g,sugar_g,sodium_mg,is_common,data_source,embedding)
                            VALUES (:n,:e,:a,:c,:kcal,:p,:f,:cb,:fb,:sug,:na,true,'中国食物成分表',:emb::vector)
                            ON CONFLICT (name_zh) DO NOTHING"""),
                            {"n":f["n"],"e":f["e"],"a":f.get("a",[]),"c":cid,"kcal":f["kcal"],"p":f["p"],"f":f["f"],"cb":f["cb"],"fb":f.get("fb",0),"sug":f.get("sug",0),"na":f.get("na",0),"emb":emb_str}
                        )
                        added += 1
                    except Exception:
                        skipped += 1

                await conn.commit()

                # Regenerate embeddings for existing foods that have null embedding
                fixed = 0
                r = await conn.execute(sa_text("SELECT id, name_zh, alias FROM foods WHERE embedding IS NULL"))
                null_rows = r.fetchall()
                for row in null_rows:
                    try:
                        emb_text = row[1]
                        if row[2] and len(row[2]) > 0:
                            emb_text += " 别名: " + ", ".join(row[2])
                        vec = await embedding_gen.embed_text(emb_text)
                        emb_str = embedding_gen.embedding_to_pgvector_string(vec)
                        await conn.execute(sa_text("UPDATE foods SET embedding=:e::vector WHERE id=:id"), {"e":emb_str,"id":row[0]})
                        fixed += 1
                    except Exception:
                        pass
                await conn.commit()

                result["status"] = "done"
                result["added"] = added
                result["skipped"] = skipped
                result["embeddings_fixed"] = fixed
                result["total"] = added + skipped
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)[:300]
        return result

    return app

def _safe_url(url: str) -> str:
    """Mask password in connection URL for safe logging."""
    if "@" in url:
        parts = url.split("@")
        return f"...@{parts[-1]}"
    return url


# ── Direct run ──────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:create_app", host="0.0.0.0", port=8000, reload=True, factory=True)

# ── Local uvicorn: `uvicorn app.main:app` needs top-level `app` ──
elif not _IS_SERVERLESS:
    app = create_app()

# ── Vercel: `api/index.py` calls create_app() — no top-level app needed ──
