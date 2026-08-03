"""
NutriAgent — MVP Food Database Seed

Run: python seed_foods.py

Imports ~80 common Chinese foods with nutrition data and pgvector embeddings.
Uses existing embedding tool (app/tools/embedding.py) for vector generation.
Idempotent: safe to re-run (ON CONFLICT skip duplicates).

Prerequisites:
  ALTER TABLE foods ADD CONSTRAINT IF NOT EXISTS foods_name_zh_key UNIQUE (name_zh);
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import asyncpg
from app.config import settings


# ── Connection config ───────────────────────────────

DB_URL = settings.DATABASE_URL.replace("+asyncpg", "").replace("+psycopg2", "")


# ── MVP Food Data (basic ingredients only, no complex dishes) ─

SEED_FOODS = [
    # ── Staples (主食) ──
    {"name_zh":"白米饭","name_en":"Steamed Rice","alias":["米饭","大米饭"],"category":"staple","energy_kcal":116,"protein_g":2.6,"fat_g":0.3,"carbs_g":25.6,"fiber_g":0.3,"sugar_g":0.1,"sodium_mg":2},
    {"name_zh":"馒头","name_en":"Steamed Bun","alias":["馍馍","白面馒头"],"category":"staple","energy_kcal":223,"protein_g":7.0,"fat_g":1.1,"carbs_g":44.2,"fiber_g":1.3,"sugar_g":2.0,"sodium_mg":165},
    {"name_zh":"面条","name_en":"Noodles","alias":["挂面","切面","白面条"],"category":"staple","energy_kcal":284,"protein_g":8.3,"fat_g":0.7,"carbs_g":61.9,"fiber_g":1.7,"sugar_g":1.0,"sodium_mg":2},
    {"name_zh":"燕麦","name_en":"Oats","alias":["燕麦片","燕麦粥"],"category":"staple","energy_kcal":377,"protein_g":13.5,"fat_g":6.7,"carbs_g":61.6,"fiber_g":10.6,"sugar_g":0.9,"sodium_mg":2},
    {"name_zh":"全麦面包","name_en":"Whole Wheat Bread","alias":["全麦吐司","黑面包"],"category":"staple","energy_kcal":247,"protein_g":13.0,"fat_g":3.4,"carbs_g":41.3,"fiber_g":7.0,"sugar_g":4.0,"sodium_mg":400},
    {"name_zh":"红薯","name_en":"Sweet Potato","alias":["地瓜","番薯","甘薯"],"category":"staple","energy_kcal":86,"protein_g":1.6,"fat_g":0.1,"carbs_g":20.1,"fiber_g":3.0,"sugar_g":4.2,"sodium_mg":55},
    {"name_zh":"玉米","name_en":"Corn","alias":["玉米棒","苞米"],"category":"staple","energy_kcal":112,"protein_g":4.0,"fat_g":1.2,"carbs_g":22.8,"fiber_g":2.8,"sugar_g":3.2,"sodium_mg":2},
    {"name_zh":"小米粥","name_en":"Millet Porridge","alias":["小米","黄米粥"],"category":"staple","energy_kcal":46,"protein_g":1.4,"fat_g":0.7,"carbs_g":8.4,"fiber_g":0.7,"sugar_g":0.1,"sodium_mg":2},

    # ── Meats (肉类) ──
    {"name_zh":"猪肉","name_en":"Pork","alias":["瘦肉","猪瘦肉"],"category":"meat","energy_kcal":143,"protein_g":20.3,"fat_g":6.2,"carbs_g":1.5,"fiber_g":0,"sugar_g":0,"sodium_mg":57},
    {"name_zh":"牛肉","name_en":"Beef","alias":["牛瘦肉","牛里脊"],"category":"meat","energy_kcal":125,"protein_g":19.9,"fat_g":4.2,"carbs_g":2.0,"fiber_g":0,"sugar_g":0,"sodium_mg":84},
    {"name_zh":"羊肉","name_en":"Lamb","alias":["羊瘦肉","羊腿肉"],"category":"meat","energy_kcal":203,"protein_g":19.0,"fat_g":14.1,"carbs_g":0,"fiber_g":0,"sugar_g":0,"sodium_mg":80},
    {"name_zh":"鸡胸肉","name_en":"Chicken Breast","alias":["鸡脯肉","鸡肉","鸡大胸"],"category":"poultry","energy_kcal":133,"protein_g":31.0,"fat_g":1.2,"carbs_g":0,"fiber_g":0,"sugar_g":0,"sodium_mg":45},
    {"name_zh":"鸡腿","name_en":"Chicken Leg","alias":["鸡腿肉","琵琶腿"],"category":"poultry","energy_kcal":181,"protein_g":16.0,"fat_g":13.0,"carbs_g":0,"fiber_g":0,"sugar_g":0,"sodium_mg":60},
    {"name_zh":"鸭肉","name_en":"Duck","alias":["鸭胸肉"],"category":"poultry","energy_kcal":240,"protein_g":15.5,"fat_g":19.7,"carbs_g":0.2,"fiber_g":0,"sugar_g":0,"sodium_mg":70},
    {"name_zh":"猪排骨","name_en":"Pork Ribs","alias":["排骨","猪小排"],"category":"meat","energy_kcal":264,"protein_g":18.3,"fat_g":20.4,"carbs_g":1.7,"fiber_g":0,"sugar_g":0,"sodium_mg":62},

    # ── Seafood (水产) ──
    {"name_zh":"三文鱼","name_en":"Salmon","alias":["鲑鱼","大马哈鱼"],"category":"seafood","energy_kcal":208,"protein_g":20.4,"fat_g":13.4,"carbs_g":0,"fiber_g":0,"sugar_g":0,"sodium_mg":59},
    {"name_zh":"虾仁","name_en":"Shrimp","alias":["虾","大虾","对虾","基围虾"],"category":"seafood","energy_kcal":99,"protein_g":20.3,"fat_g":0.7,"carbs_g":0.2,"fiber_g":0,"sugar_g":0,"sodium_mg":150},
    {"name_zh":"带鱼","name_en":"Hairtail","alias":["刀鱼","白带鱼"],"category":"seafood","energy_kcal":127,"protein_g":17.7,"fat_g":4.9,"carbs_g":3.1,"fiber_g":0,"sugar_g":0,"sodium_mg":110},
    {"name_zh":"金枪鱼","name_en":"Tuna","alias":["吞拿鱼","鲔鱼"],"category":"seafood","energy_kcal":144,"protein_g":23.3,"fat_g":4.9,"carbs_g":0,"fiber_g":0,"sugar_g":0,"sodium_mg":39},
    {"name_zh":"鲈鱼","name_en":"Sea Bass","alias":["花鲈","清蒸鲈鱼"],"category":"seafood","energy_kcal":105,"protein_g":18.6,"fat_g":3.4,"carbs_g":0,"fiber_g":0,"sugar_g":0,"sodium_mg":80},

    # ── Eggs & Dairy (蛋奶) ──
    {"name_zh":"鸡蛋","name_en":"Egg","alias":["鸡蛋黄","煮鸡蛋","炒鸡蛋","蛋"],"category":"egg","energy_kcal":144,"protein_g":13.3,"fat_g":8.8,"carbs_g":2.8,"fiber_g":0,"sugar_g":0.5,"sodium_mg":131},
    {"name_zh":"牛奶","name_en":"Milk","alias":["鲜奶","全脂牛奶","纯牛奶"],"category":"dairy","energy_kcal":54,"protein_g":3.0,"fat_g":3.2,"carbs_g":3.4,"fiber_g":0,"sugar_g":3.4,"sodium_mg":41},
    {"name_zh":"酸奶","name_en":"Yogurt","alias":["酸牛奶","优格","优酪乳"],"category":"dairy","energy_kcal":72,"protein_g":2.5,"fat_g":2.7,"carbs_g":9.3,"fiber_g":0,"sugar_g":9.3,"sodium_mg":40},
    {"name_zh":"豆浆","name_en":"Soy Milk","alias":["豆奶","现磨豆浆"],"category":"dairy","energy_kcal":31,"protein_g":3.0,"fat_g":1.6,"carbs_g":1.2,"fiber_g":1.2,"sugar_g":0.5,"sodium_mg":2},
    {"name_zh":"豆腐","name_en":"Tofu","alias":["嫩豆腐","老豆腐","北豆腐"],"category":"legume","energy_kcal":81,"protein_g":8.1,"fat_g":3.7,"carbs_g":4.2,"fiber_g":0.4,"sugar_g":0.5,"sodium_mg":7},

    # ── Vegetables (蔬菜) ──
    {"name_zh":"番茄","name_en":"Tomato","alias":["西红柿","西红柿"],"category":"vegetable","energy_kcal":20,"protein_g":0.9,"fat_g":0.2,"carbs_g":3.5,"fiber_g":1.2,"sugar_g":2.6,"sodium_mg":5},
    {"name_zh":"黄瓜","name_en":"Cucumber","alias":["青瓜","胡瓜"],"category":"vegetable","energy_kcal":16,"protein_g":0.7,"fat_g":0.1,"carbs_g":2.9,"fiber_g":0.5,"sugar_g":1.6,"sodium_mg":2},
    {"name_zh":"白菜","name_en":"Chinese Cabbage","alias":["大白菜","小白菜","娃娃菜"],"category":"vegetable","energy_kcal":13,"protein_g":1.5,"fat_g":0.2,"carbs_g":2.2,"fiber_g":0.8,"sugar_g":1.0,"sodium_mg":8},
    {"name_zh":"菠菜","name_en":"Spinach","alias":["菠菜","赤根菜"],"category":"vegetable","energy_kcal":28,"protein_g":2.6,"fat_g":0.3,"carbs_g":4.5,"fiber_g":2.2,"sugar_g":0.4,"sodium_mg":85},
    {"name_zh":"西兰花","name_en":"Broccoli","alias":["花椰菜","青花菜","花菜"],"category":"vegetable","energy_kcal":36,"protein_g":4.1,"fat_g":0.6,"carbs_g":4.3,"fiber_g":1.6,"sugar_g":1.7,"sodium_mg":27},
    {"name_zh":"胡萝卜","name_en":"Carrot","alias":["红萝卜","胡萝卜"],"category":"vegetable","energy_kcal":37,"protein_g":1.0,"fat_g":0.2,"carbs_g":8.8,"fiber_g":2.8,"sugar_g":4.7,"sodium_mg":71},
    {"name_zh":"生菜","name_en":"Lettuce","alias":["叶生菜","球生菜","罗马生菜"],"category":"vegetable","energy_kcal":13,"protein_g":1.3,"fat_g":0.3,"carbs_g":1.3,"fiber_g":1.3,"sugar_g":0.6,"sodium_mg":25},
    {"name_zh":"土豆","name_en":"Potato","alias":["马铃薯","洋芋","薯仔"],"category":"vegetable","energy_kcal":81,"protein_g":2.0,"fat_g":0.2,"carbs_g":17.5,"fiber_g":2.1,"sugar_g":0.8,"sodium_mg":6},
    {"name_zh":"茄子","name_en":"Eggplant","alias":["矮瓜","落苏"],"category":"vegetable","energy_kcal":21,"protein_g":1.1,"fat_g":0.2,"carbs_g":4.9,"fiber_g":1.3,"sugar_g":2.4,"sodium_mg":2},
    {"name_zh":"青椒","name_en":"Green Pepper","alias":["甜椒","柿子椒","灯笼椒"],"category":"vegetable","energy_kcal":22,"protein_g":1.0,"fat_g":0.2,"carbs_g":4.6,"fiber_g":1.7,"sugar_g":2.4,"sodium_mg":3},

    # ── Fruits (水果) ──
    {"name_zh":"苹果","name_en":"Apple","alias":["红富士","嘎啦苹果"],"category":"fruit","energy_kcal":53,"protein_g":0.3,"fat_g":0.2,"carbs_g":13.8,"fiber_g":2.4,"sugar_g":10.4,"sodium_mg":1},
    {"name_zh":"香蕉","name_en":"Banana","alias":["大蕉","芭蕉"],"category":"fruit","energy_kcal":93,"protein_g":1.1,"fat_g":0.2,"carbs_g":22.8,"fiber_g":2.6,"sugar_g":12.2,"sodium_mg":1},
    {"name_zh":"橙子","name_en":"Orange","alias":["甜橙","脐橙"],"category":"fruit","energy_kcal":48,"protein_g":0.9,"fat_g":0.1,"carbs_g":11.8,"fiber_g":2.4,"sugar_g":9.4,"sodium_mg":1},
    {"name_zh":"西瓜","name_en":"Watermelon","alias":["西瓜","8424"],"category":"fruit","energy_kcal":31,"protein_g":0.6,"fat_g":0.1,"carbs_g":7.6,"fiber_g":0.4,"sugar_g":6.2,"sodium_mg":1},
    {"name_zh":"葡萄","name_en":"Grape","alias":["提子","红提"],"category":"fruit","energy_kcal":44,"protein_g":0.5,"fat_g":0.2,"carbs_g":10.3,"fiber_g":0.9,"sugar_g":8.5,"sodium_mg":2},
    {"name_zh":"草莓","name_en":"Strawberry","alias":["士多啤梨","红莓"],"category":"fruit","energy_kcal":32,"protein_g":0.7,"fat_g":0.3,"carbs_g":7.7,"fiber_g":2.0,"sugar_g":4.9,"sodium_mg":1},
    {"name_zh":"蓝莓","name_en":"Blueberry","alias":["蓝莓","越橘"],"category":"fruit","energy_kcal":57,"protein_g":0.7,"fat_g":0.3,"carbs_g":14.5,"fiber_g":2.4,"sugar_g":10.0,"sodium_mg":1},
    {"name_zh":"猕猴桃","name_en":"Kiwi","alias":["奇异果","猕猴桃"],"category":"fruit","energy_kcal":61,"protein_g":1.1,"fat_g":0.5,"carbs_g":14.7,"fiber_g":3.0,"sugar_g":9.0,"sodium_mg":3},

    # ── Nuts & Seeds (坚果) ──
    {"name_zh":"核桃","name_en":"Walnut","alias":["胡桃","核桃仁"],"category":"nut","energy_kcal":646,"protein_g":14.9,"fat_g":58.8,"carbs_g":19.1,"fiber_g":9.5,"sugar_g":2.6,"sodium_mg":2},
    {"name_zh":"花生","name_en":"Peanut","alias":["花生米","落花生"],"category":"nut","energy_kcal":567,"protein_g":25.8,"fat_g":49.2,"carbs_g":16.1,"fiber_g":8.5,"sugar_g":4.7,"sodium_mg":18},
    {"name_zh":"杏仁","name_en":"Almond","alias":["巴旦木","扁桃仁"],"category":"nut","energy_kcal":578,"protein_g":21.2,"fat_g":49.9,"carbs_g":21.6,"fiber_g":12.5,"sugar_g":4.4,"sodium_mg":1},

    # ── Beverages (饮品) ──
    {"name_zh":"咖啡","name_en":"Coffee","alias":["美式","黑咖啡","清咖"],"category":"beverage","energy_kcal":2,"protein_g":0.1,"fat_g":0,"carbs_g":0,"fiber_g":0,"sugar_g":0,"sodium_mg":2},
    {"name_zh":"绿茶","name_en":"Green Tea","alias":["茶","龙井","碧螺春"],"category":"beverage","energy_kcal":1,"protein_g":0,"fat_g":0,"carbs_g":0.2,"fiber_g":0,"sugar_g":0,"sodium_mg":1},
    {"name_zh":"可乐","name_en":"Cola","alias":["可口可乐","百事可乐","汽水"],"category":"beverage","energy_kcal":42,"protein_g":0,"fat_g":0,"carbs_g":10.6,"fiber_g":0,"sugar_g":10.6,"sodium_mg":4},

    # ── Condiments (调味品) ──
    {"name_zh":"酱油","name_en":"Soy Sauce","alias":["生抽","老抽","豉油"],"category":"condiment","energy_kcal":63,"protein_g":5.6,"fat_g":0.1,"carbs_g":10.1,"fiber_g":0,"sugar_g":1.5,"sodium_mg":5757},
    {"name_zh":"食用油","name_en":"Cooking Oil","alias":["花生油","菜籽油","大豆油","色拉油"],"category":"oil","energy_kcal":899,"protein_g":0,"fat_g":99.9,"carbs_g":0,"fiber_g":0,"sugar_g":0,"sodium_mg":0},
    {"name_zh":"盐","name_en":"Salt","alias":["食盐","海盐","精盐"],"category":"condiment","energy_kcal":0,"protein_g":0,"fat_g":0,"carbs_g":0,"fiber_g":0,"sugar_g":0,"sodium_mg":38758},
]


# ── Main ────────────────────────────────────────────

async def seed():
    conn = await asyncpg.connect(DB_URL, statement_cache_size=0)
    print(f"Connected to: {DB_URL.split('@')[-1] if '@' in DB_URL else DB_URL}")

    # Use existing embedding tool
    from app.tools.embedding import embedding_gen

    category_map = {}
    rows = await conn.fetch("SELECT category, id FROM food_categories")
    for row in rows:
        category_map[row["category"]] = row["id"]

    added = 0
    skipped = 0
    embed_failed = 0

    for food in SEED_FOODS:
        cat_id = category_map.get(food["category"])
        if cat_id is None:
            print(f"  SKIP: unknown category '{food['category']}' — {food['name_zh']}")
            continue

        # Generate embedding from name + alias + category
        embed_text = food["name_zh"]
        if food.get("alias"):
            embed_text += " 别名: " + ", ".join(food["alias"])
        embed_text += f" 类别: {food['category']}"

        emb_str = None
        try:
            vec = await embedding_gen.embed_text(embed_text)
            emb_str = embedding_gen.embedding_to_pgvector_string(vec)
        except Exception as e:
            embed_failed += 1
            print(f"  EMBED FAIL: {food['name_zh']} — {e}")

        try:
            await conn.execute(
                """INSERT INTO foods (name_zh, name_en, alias, category_id,
                   energy_kcal, protein_g, fat_g, carbs_g, fiber_g, sugar_g, sodium_mg,
                   is_common, data_source, embedding)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,true,'中国食物成分表',
                   $12::vector)
                   ON CONFLICT (name_zh) DO NOTHING""",
                food["name_zh"], food["name_en"], food.get("alias", []), cat_id,
                food["energy_kcal"], food["protein_g"], food["fat_g"], food["carbs_g"],
                food.get("fiber_g", 0), food.get("sugar_g", 0), food.get("sodium_mg", 0),
                emb_str,
            )
            added += 1
        except asyncpg.exceptions.UniqueViolationError:
            skipped += 1
        except Exception as e:
            print(f"  INSERT FAIL: {food['name_zh']} — {e}")
            skipped += 1

    await conn.close()

    print(f"\nDone: +{added} new, ~{skipped} skipped, {embed_failed} embed failures")
    print(f"Total foods in DB: ~{added} (skipped existing)")


if __name__ == "__main__":
    asyncio.run(seed())
