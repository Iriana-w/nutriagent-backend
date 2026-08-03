"""
NutriAgent -- 产品验收测试 (Product Acceptance Test)
====================================================
模拟完整用户生命周期，端到端验证生产环境 API。

覆盖范围:
  - 注册与认证 (Registration & Authentication)
  - 健康档案管理 (Health Profile)
  - 健康目标 / 饮食类型 / 过敏源 (Goals / Diet Types / Allergens)
  - 食物偏好 (Food Preferences)
  - 位置服务 GPS + 手动 (Location)
  - FoodParserAgent (自然语言 -> 结构化食物数据)
  - 饮食记录 CRUD
  - 营养看板与周报
  - RecommendationAgent (个性化下一餐推荐)
  - 对话 (偏好表达 + AI 回复)
  - 数据持久化验证 (回读检查)

运行:  python test_acceptance.py
"""

import json
import sys
import time
import requests

# --- 配置 ---
BASE = "https://nutriagent-backend.vercel.app/api/v1"
HEADERS = {"Content-Type": "application/json"}
TIMEOUT = 90  # Agent 调用可能较慢 (LangGraph pipeline 冷启动)

# --- 计数器 ---
PASS = 0
FAIL = 0
SKIP = 0


# --- 辅助函数 ---
def _status(r, expect, label, detail=""):
    """检查指定 HTTP 状态码并输出结果。"""
    global PASS, FAIL, SKIP
    if r is None:
        FAIL += 1
        print(f"  [失败] {label} -- 网络错误" + (f" | {detail}" if detail else ""))
        return False
    if r.status_code == expect:
        PASS += 1
        print(f"  [通过] {label}" + (f" -- {detail}" if detail else ""))
        return True
    else:
        FAIL += 1
        body = ""
        try:
            body = r.text[:150]
        except Exception:
            pass
        print(f"  [失败] {label} -- 期望 {expect}, 实际 {r.status_code}" + (f" | {detail}" if detail else ""))
        if body:
            print(f"         {body}")
        return False


def _ok(r, label, detail=""):
    """检查 2xx 状态码并输出结果。"""
    global PASS, FAIL
    if r is None:
        FAIL += 1
        print(f"  [失败] {label} -- 网络错误" + (f" | {detail}" if detail else ""))
        return False
    if 200 <= r.status_code < 300:
        PASS += 1
        print(f"  [通过] {label}" + (f" -- {detail}" if detail else ""))
        return True
    else:
        FAIL += 1
        body = ""
        try:
            body = r.text[:150]
        except Exception:
            pass
        print(f"  [失败] {label} -- 期望 2xx, 实际 {r.status_code}" + (f" | {detail}" if detail else ""))
        if body:
            print(f"         {body}")
        return False


def _post(path, body, auth=True):
    """发送 POST 请求, 可选鉴权。"""
    h = dict(HEADERS)
    if auth and TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    try:
        r = requests.post(f"{BASE}{path}", json=body, headers=h, timeout=TIMEOUT)
        return r
    except Exception as e:
        print(f"     [异常] POST {path}: {e}")
        return None


def _get(path, auth=True):
    """发送 GET 请求, 可选鉴权。"""
    h = dict(HEADERS)
    if auth and TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    try:
        r = requests.get(f"{BASE}{path}", headers=h, timeout=TIMEOUT)
        return r
    except Exception as e:
        print(f"     [异常] GET {path}: {e}")
        return None


def _put(path, body, auth=True):
    """发送 PUT 请求, 可选鉴权。"""
    h = dict(HEADERS)
    if auth and TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    try:
        r = requests.put(f"{BASE}{path}", json=body, headers=h, timeout=TIMEOUT)
        return r
    except Exception as e:
        print(f"     [异常] PUT {path}: {e}")
        return None


def _patch(path, body, auth=True):
    """发送 PATCH 请求, 可选鉴权。"""
    h = dict(HEADERS)
    if auth and TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    try:
        r = requests.patch(f"{BASE}{path}", json=body, headers=h, timeout=TIMEOUT)
        return r
    except Exception as e:
        print(f"     [异常] PATCH {path}: {e}")
        return None


# --- 全局状态 ---
TOKEN = None
UID = None
FOOD_LOG_ID = None
CHAT_SESSION_ID = None
PARSED_ITEMS = []


# ====================================================================
# 第 0 幕 -- 系统健康检查 (无鉴权)
# ====================================================================
print("=" * 60)
print("  NutriAgent -- 产品验收测试")
print("=" * 60)

print("\n-- 第 0 幕: 系统健康检查 --")
r = _get("/health", auth=False)
_ok(r, "0.1 健康端点", f"status={r.json().get('status','?') if r else 'N/A'}")

# ====================================================================
# 第 1 幕 -- 注册 + 登录
# ====================================================================
print("\n-- 第 1 幕: 注册与认证 --")
ts = int(time.time())
EMAIL = f"accept-{ts}@example.com"
PASSWORD = "TestPass123"
NICKNAME = f"QA-{ts}"

# 1.1 注册
r = _post("/auth/register", {
    "nickname": NICKNAME,
    "email": EMAIL,
    "password": PASSWORD,
    "gender": "male",
}, auth=False)
ok = r is not None and r.status_code == 201 and bool(r.json().get("access_token"))
if ok:
    TOKEN = r.json()["access_token"]
    PASS += 1
    print(f"  [通过] 1.1 注册 -- token={TOKEN[:16]}... 有效期={r.json().get('expires_in')}秒")
else:
    FAIL += 1
    body = r.text[:200] if r else "无响应"
    print(f"  [失败] 1.1 注册 -- {body}")
    print("  无法获取 token, 测试终止。")
    sys.exit(1)

# 1.2 登录 (验证凭据可用)
r = _post("/auth/login", {"email": EMAIL, "password": PASSWORD}, auth=False)
if _ok(r, "1.2 登录"):
    TOKEN = r.json()["access_token"]

# 1.3 错误密码登录 (应返回 401)
r = _post("/auth/login", {"email": EMAIL, "password": "WrongPass999"}, auth=False)
_status(r, 401, "1.3 错误密码登录 -> 401")

# 1.4 无鉴权访问 /users/me (应被拒绝)
r = _get("/users/me", auth=False)
if r is not None and r.status_code in (401, 403):
    PASS += 1
    print(f"  [通过] 1.4 无鉴权 GET /users/me -> {r.status_code} (正确拒绝)")
else:
    FAIL += 1
    print(f"  [失败] 1.4 无鉴权 GET /users/me -- 期望 401/403, 实际 {r.status_code if r else 'error'}")


# ====================================================================
# 第 2 幕 -- 健康档案
# ====================================================================
print("\n-- 第 2 幕: 健康档案 --")

# 2.1 获取当前用户
r = _get("/users/me")
if r and r.ok:
    UID = r.json().get("id")
    PASS += 1
    print(f"  [通过] 2.1 GET /users/me -- id={UID[:12]}..., 昵称={r.json().get('nickname')}")
else:
    FAIL += 1
    print(f"  [失败] 2.1 GET /users/me")

# 2.2 更新健康档案
r = _patch("/users/me/health-profile", {
    "height_cm": 178,
    "weight_kg": 82,
    "daily_kcal_target": 2500,
    "target_protein_pct": 30,
    "target_fat_pct": 25,
    "target_carbs_pct": 45,
    "activity_level": "moderate",
    "body_fat_pct": 18,
})
ok = r is not None and r.status_code == 200
if ok:
    hp = r.json()
    PASS += 1
    bmi = hp.get("bmi")
    bmr = hp.get("bmr_kcal")
    print(f"  [通过] 2.2 更新健康档案 -- BMI={bmi}, BMR={bmr}, 目标热量={hp.get('daily_kcal_target')}kcal")
else:
    FAIL += 1
    print(f"  [失败] 2.2 更新健康档案 -- status={r.status_code if r else 'error'}")


# ====================================================================
# 第 3 幕 -- 健康目标 / 饮食类型 / 过敏源
# ====================================================================
print("\n-- 第 3 幕: 健康目标, 饮食类型, 过敏源 --")

# 3.1 设置健康目标
r = _put("/users/me/health-goals", [
    {"goal_type": "gain_muscle",    "priority": 9, "is_active": True},
    {"goal_type": "eye_health",     "priority": 7, "is_active": True},
    {"goal_type": "energy_boost",   "priority": 5, "is_active": True},
])
ok = r is not None and r.status_code == 200
if ok:
    goals = r.json()
    PASS += 1
    print(f"  [通过] 3.1 设置健康目标 -- {len(goals)} 个: {[g['goal_type'] for g in goals]}")
else:
    FAIL += 1
    print(f"  [失败] 3.1 设置健康目标 -- status={r.status_code if r else 'error'}")

# 3.2 设置饮食类型
r = _put("/users/me/diet-types", [
    {"diet_type": "keto",       "is_primary": True},
    {"diet_type": "low_carb",   "is_primary": False},
])
_ok(r, "3.2 设置饮食类型")

# 3.3 设置过敏源
r = _put("/users/me/allergens", [
    {"allergen": "peanut",  "severity": "moderate", "notes": "轻微过敏"},
    {"allergen": "shrimp",  "severity": "mild",     "notes": "偶尔不适"},
])
_ok(r, "3.3 设置过敏源")


# ====================================================================
# 第 4 幕 -- 食物偏好
# ====================================================================
print("\n-- 第 4 幕: 食物偏好 --")

# 4.1 获取初始偏好
r = _get("/users/me/preferences")
_ok(r, "4.1 获取偏好(初始值)")

# 4.2 更新偏好
r = _patch("/users/me/preferences", {
    "spice_level": 3,
    "oil_level": 2,
    "sweet_level": 1,
    "budget_per_meal": 3500,
    "food_blacklist": ["香菜", "芹菜"],
    "food_whitelist": ["鸡胸肉", "三文鱼", "西兰花"],
    "cuisine_prefs": {"preferred": ["中式", "日式"], "avoid": ["油炸"]},
})
_ok(r, "4.2 更新偏好 -- 辣度=3, 油度=2, 预算=3500, 黑名单+白名单")

# 4.3 回读验证偏好持久化
r = _get("/users/me/preferences")
if r and r.ok:
    prefs = r.json()
    spice_ok = prefs.get("spice_level") == 3
    budget_ok = prefs.get("budget_per_meal") == 3500
    if spice_ok and budget_ok:
        PASS += 1
        print(f"  [通过] 4.3 偏好持久化验证 -- 辣度={prefs.get('spice_level')}, 预算={prefs.get('budget_per_meal')}分")
    else:
        FAIL += 1
        print(f"  [失败] 4.3 偏好持久化验证 -- 辣度={prefs.get('spice_level')}(期望3), 预算={prefs.get('budget_per_meal')}(期望3500)")
else:
    FAIL += 1
    print(f"  [失败] 4.3 偏好持久化验证 -- status={r.status_code if r else 'error'}")


# ====================================================================
# 第 5 幕 -- 位置服务 (GPS + 手动)
# ====================================================================
print("\n-- 第 5 幕: 位置服务 --")

# 5.1 GPS 定位更新 (上海)
r = _post("/location/update", {"latitude": 31.2304, "longitude": 121.4737})
if _ok(r, "5.1 GPS定位更新(上海)"):
    loc = r.json()
    print(f"       城市={loc.get('city')}, 区={loc.get('district')}, 省={loc.get('province')}")

# 5.2 获取当前位置
r = _get("/location/current")
if r and r.ok:
    loc = r.json()
    has_coords = loc.get("latitude") is not None and loc.get("longitude") is not None
    if has_coords:
        PASS += 1
        print(f"  [通过] 5.2 获取当前位置 -- 纬度={loc['latitude']}, 经度={loc['longitude']}, 城市={loc.get('city','?')}")
    else:
        FAIL += 1
        print(f"  [失败] 5.2 获取当前位置 -- 坐标未保存")
else:
    FAIL += 1
    print(f"  [失败] 5.2 获取当前位置 -- status={r.status_code if r else 'error'}")

# 5.3 手动设置城市 (杭州)
r = _post("/location/manual", {"city": "杭州", "province": "浙江省", "adcode": "330100"})
_ok(r, "5.3 手动设置位置(杭州)")


# ====================================================================
# 第 6 幕 -- FoodParserAgent (AI 食物解析)
# ====================================================================
print("\n-- 第 6 幕: FoodParserAgent (AI 食物解析) --")

# 6.1 解析早餐
print("  [6.1] 解析: 早餐吃了两个鸡蛋、一杯牛奶和一个苹果...")
r = _post("/food-logs/parse", {"text": "早餐吃了两个鸡蛋、一杯牛奶和一个苹果"}, auth=False)
if r and r.ok:
    data = r.json()
    items = data.get("items", [])
    total_kcal = data.get("total_kcal", 0)
    parse_ms = data.get("parse_time_ms", 0)

    if len(items) >= 2:
        PASS += 1
        print(f"  [通过] 6.1 早餐解析 -- {len(items)} 项, {total_kcal:.0f} kcal, 耗时 {parse_ms}ms")
    else:
        FAIL += 1
        print(f"  [失败] 6.1 早餐解析 -- 仅解析出 {len(items)} 项 (期望 >=2)")

    for item in items:
        name = item.get("food_name", "?")
        qty = item.get("quantity", "?")
        unit = item.get("unit", "?")
        grams = item.get("serving_size_g", 0)
        kcal = item.get("energy_kcal", 0)
        conf = item.get("confidence", 0)
        src = item.get("source", "?")
        flag = "[OK]" if conf >= 0.5 and grams > 0 and kcal > 0 else "[?]"
        print(f"       {flag} {name} x{qty}{unit}  {grams}g  {kcal}kcal  置信度={conf:.2f}  来源={src}")

    PARSED_ITEMS = items
else:
    FAIL += 1
    body = r.text[:200] if r else "无响应"
    print(f"  [失败] 6.1 早餐解析 -- status={r.status_code if r else 'error'}: {body}")

# 6.2 解析午餐
print("  [6.2] 解析: 中午吃了一份宫保鸡丁和一碗米饭...")
r = _post("/food-logs/parse", {"text": "中午吃了一份宫保鸡丁和一碗米饭"}, auth=False)
if r and r.ok:
    data = r.json()
    items = data.get("items", [])
    if len(items) >= 1:
        PASS += 1
        print(f"  [通过] 6.2 午餐解析 -- {len(items)} 项, {data.get('total_kcal', 0):.0f} kcal")
    else:
        FAIL += 1
        print(f"  [失败] 6.2 午餐解析 -- 0 项")
    for item in items:
        print(f"       {item.get('food_name','?')} x{item.get('quantity','?')}{item.get('unit','?')}  "
              f"{item.get('serving_size_g',0)}g  {item.get('energy_kcal',0)}kcal  置信度={item.get('confidence',0):.2f}")
else:
    FAIL += 1
    print(f"  [失败] 6.2 午餐解析 -- status={r.status_code if r else 'error'}")

# 6.3 边界测试: 空文本
print("  [6.3] 空文本 (应返回 422)...")
r = _post("/food-logs/parse", {"text": ""}, auth=False)
_status(r, 422, "6.3 空文本解析 -> 422")


# ====================================================================
# 第 7 幕 -- 饮食记录 (创建, 列表, 单条查询)
# ====================================================================
print("\n-- 第 7 幕: 饮食记录 --")

# 7.1 手动创建饮食记录
print("  [7.1] 手动录入午餐...")
r = _post("/food-logs", {
    "meal_type": "lunch",
    "source": "manual",
    "notes": "验收测试 - 手动录入",
    "items": [
        {
            "food_name": "测试鸡胸肉", "serving_size_g": 200, "energy_kcal": 266,
            "protein_g": 62, "fat_g": 2.4, "carbs_g": 0,
            "fiber_g": 0, "sodium_mg": 90, "caffeine_mg": 0,
            "quantity": 1, "serving_unit": "份", "sort_order": 0,
        },
        {
            "food_name": "测试西兰花", "serving_size_g": 150, "energy_kcal": 54,
            "protein_g": 6.2, "fat_g": 0.9, "carbs_g": 6.5,
            "fiber_g": 2.4, "sodium_mg": 40, "caffeine_mg": 0,
            "quantity": 1, "serving_unit": "份", "sort_order": 1,
        },
    ],
})
if r and r.status_code == 201:
    data = r.json()
    FOOD_LOG_ID = data.get("id")
    PASS += 1
    total_kcal = data.get("total_kcal", 0)
    items_count = len(data.get("items", []))
    print(f"  [通过] 7.1 手动录入 -- id={FOOD_LOG_ID[:12]}..., 项数={items_count}, 总热量={total_kcal:.0f}kcal")
else:
    FAIL += 1
    print(f"  [失败] 7.1 手动录入 -- status={r.status_code if r else 'error'}")
    if r:
        print(f"     {r.text[:200]}")

# 7.2 从 AI 解析结果保存饮食记录
if PARSED_ITEMS:
    print("  [7.2] 从 AI 解析结果保存早餐...")
    payload = {
        "meal_type": "breakfast",
        "source": "ai_estimate",
        "notes": "验收测试 - AI 解析",
        "items": [
            {
                "food_name": item["food_name"],
                "food_id": item.get("food_id"),
                "quantity": item.get("quantity", 1),
                "serving_unit": item.get("unit", "g"),
                "serving_size_g": item["serving_size_g"],
                "energy_kcal": item["energy_kcal"],
                "protein_g": item.get("protein_g", 0),
                "fat_g": item.get("fat_g", 0),
                "carbs_g": item.get("carbs_g", 0),
                "fiber_g": item.get("fiber_g", 0),
                "sodium_mg": item.get("sodium_mg", 0),
                "caffeine_mg": item.get("caffeine_mg", 0),
                "confidence": item.get("confidence", 0.5),
                "sort_order": idx,
            }
            for idx, item in enumerate(PARSED_ITEMS)
        ],
    }
    r = _post("/food-logs", payload)
    _status(r, 201, "7.2 AI 解析结果保存")
else:
    SKIP += 1
    print("  [跳过] 7.2 跳过 -- 无 AI 解析结果可保存")

# 7.3 列表查询
r = _get("/food-logs?page_size=10")
if r and r.ok:
    data = r.json()
    log_count = len(data.get("items", []))
    total = data.get("total", 0)
    if log_count >= 1:
        PASS += 1
        print(f"  [通过] 7.3 饮食记录列表 -- 返回 {log_count} 条, 共 {total} 条")
    else:
        FAIL += 1
        print(f"  [失败] 7.3 饮食记录列表 -- 无记录返回 (期望 >=1)")
else:
    FAIL += 1
    print(f"  [失败] 7.3 饮食记录列表 -- status={r.status_code if r else 'error'}")

# 7.4 按 ID 查询单条
if FOOD_LOG_ID:
    r = _get(f"/food-logs/{FOOD_LOG_ID}")
    if r and r.ok:
        data = r.json()
        id_match = data.get("id") == FOOD_LOG_ID
        if id_match:
            PASS += 1
            print(f"  [通过] 7.4 单条查询 -- id 匹配, {len(data.get('items',[]))} 项食物")
        else:
            FAIL += 1
            print(f"  [失败] 7.4 单条查询 -- id 不匹配")
    else:
        FAIL += 1
        print(f"  [失败] 7.4 单条查询 -- status={r.status_code if r else 'error'}")
else:
    SKIP += 1
    print("  [跳过] 7.4 跳过 -- 无 food log ID")


# ====================================================================
# 第 8 幕 -- 营养看板与周报
# ====================================================================
print("\n-- 第 8 幕: 营养看板与报告 --")

# 8.1 营养看板
r = _get("/nutrition/dashboard")
if r and r.ok:
    dash = r.json()
    total_kcal = dash.get("total_kcal", 0)
    meal_count = dash.get("meal_count", 0)
    protein = dash.get("total_protein_g", 0)
    kcal_target = dash.get("kcal_target")
    achievement = dash.get("kcal_achievement_pct")

    PASS += 1
    print(f"  [通过] 8.1 营养看板 -- 热量={total_kcal:.0f}/{kcal_target}kcal, "
          f"蛋白质={protein:.0f}g, 餐数={meal_count}, 达成率={achievement}%")
else:
    FAIL += 1
    print(f"  [失败] 8.1 营养看板 -- status={r.status_code if r else 'error'}")

# 8.2 周报
r = _get("/nutrition/report/weekly?week_start=2026-07-27")
if r and r.ok:
    PASS += 1
    report = r.json()
    avg_kcal = report.get("avg_daily_kcal", 0)
    days = report.get("days_tracked", 0)
    print(f"  [通过] 8.2 周报 -- 日均热量={avg_kcal:.0f}kcal, 追踪天数={days}")
else:
    # 新用户无历史数据, 404 可接受
    if r and r.status_code == 404:
        PASS += 1
        print(f"  [通过] 8.2 周报 -> 404 (新用户无数据, 符合预期)")
    else:
        FAIL += 1
        print(f"  [失败] 8.2 周报 -- status={r.status_code if r else 'error'}")


# ====================================================================
# 第 9 幕 -- RecommendationAgent (AI 个性化推荐)
# ====================================================================
print("\n-- 第 9 幕: RecommendationAgent (AI 推荐) --")

# 9.1 获取下一餐推荐
print("  [9.1] 请求个性化下一餐推荐...")
r = _post("/recommendations/next-meal", {
    "daily_kcal_target": 2500,
    "target_protein_pct": 30,
    "target_fat_pct": 25,
    "target_carbs_pct": 45,
    "activity_level": "moderate",
    "health_goals": [
        {"goal_type": "gain_muscle", "priority": 9},
        {"goal_type": "eye_health",  "priority": 7},
    ],
    "budget_cent": 3500,
})

if r and r.status_code == 200:
    rec = r.json()
    n_items = len(rec.get("items", []))
    score = rec.get("goal_alignment_score", 0)
    summary = rec.get("summary_text", "")[:80]
    meal_type = rec.get("meal_type", "?")
    nutrition = rec.get("nutrition", {})
    total_kcal = nutrition.get("total_kcal", 0)
    nearby = len(rec.get("nearby_restaurants", []))

    if n_items > 0:
        PASS += 1
        print(f"  [通过] 9.1 下一餐推荐 -- {n_items} 项, 目标对齐评分={score}/100, 餐次={meal_type}")
        print(f"       营养汇总: {total_kcal:.0f}kcal  "
              f"蛋白质{nutrition.get('total_protein_g',0):.0f}g  "
              f"脂肪{nutrition.get('total_fat_g',0):.0f}g  "
              f"碳水{nutrition.get('total_carbs_g',0):.0f}g")
        print(f"       推荐摘要: {summary}...")
        print(f"       附近餐厅: {nearby} 家")

        for item in rec.get("items", []):
            tags = item.get("nutrition_tags", [])
            goals = item.get("goal_alignment", [])
            reason = (item.get("reason_text") or "")[:60]
            print(f"       + {item.get('food_name','?')}  {item.get('estimated_kcal',0):.0f}kcal  "
                  f"Y{item.get('estimated_price_cent',0)/100:.1f}  "
                  f"标签={tags}  对齐目标={goals}")
            if reason:
                print(f"         推荐理由: {reason}")
    else:
        FAIL += 1
        print(f"  [失败] 9.1 下一餐推荐 -- 返回 0 项")
        print(f"     警告: {rec.get('warnings', [])}")
else:
    FAIL += 1
    body = r.text[:300] if r else "无响应"
    print(f"  [失败] 9.1 下一餐推荐 -- status={r.status_code if r else 'error'}")
    print(f"     {body}")

# 9.2 个性化信号检查
if r and r.status_code == 200:
    rec = r.json()
    items = rec.get("items", [])
    has_tags = any(item.get("nutrition_tags") for item in items)
    has_goals = any(item.get("goal_alignment") for item in items)
    has_reason = any(item.get("reason_text") for item in items)
    has_history = bool(rec.get("history_awareness"))
    has_diversity = bool(rec.get("diversity_note"))
    has_budget = bool(rec.get("budget_analysis"))
    has_tips = len(rec.get("tips", [])) > 0

    signals = sum([has_tags, has_goals, has_reason, has_history, has_diversity, has_budget, has_tips])
    if signals >= 3:
        PASS += 1
        print(f"  [通过] 9.2 个性化信号 -- {signals}/7 项存在 "
              f"(营养标签={'Y' if has_tags else 'N'}, 目标对齐={'Y' if has_goals else 'N'}, "
              f"推荐理由={'Y' if has_reason else 'N'}, 历史感知={'Y' if has_history else 'N'}, "
              f"多样性={'Y' if has_diversity else 'N'}, 预算分析={'Y' if has_budget else 'N'}, "
              f"小贴士={'Y' if has_tips else 'N'})")
    else:
        FAIL += 1
        print(f"  [失败] 9.2 个性化信号 -- 仅 {signals}/7 项存在 (期望 >=3)")


# ====================================================================
# 第 10 幕 -- 对话 (偏好表达)
# ====================================================================
print("\n-- 第 10 幕: 对话 --")

# 10.1 创建对话 session
r = _post("/chat/sessions", {"session_type": "chat"})
if r and r.status_code == 201:
    CHAT_SESSION_ID = r.json().get("id")
    PASS += 1
    print(f"  [通过] 10.1 创建对话 -- id={CHAT_SESSION_ID[:12]}..., 类型={r.json().get('session_type')}")
else:
    FAIL += 1
    print(f"  [失败] 10.1 创建对话 -- status={r.status_code if r else 'error'}")

# 10.2 发送偏好消息
if CHAT_SESSION_ID:
    print("  [10.2] 发送偏好消息: 我不吃香菜, 最喜欢吃鸡肉和牛肉, 最近在健身增肌...")
    r = _post(f"/chat/sessions/{CHAT_SESSION_ID}/messages", {
        "content": "我不吃香菜, 最喜欢吃鸡肉和牛肉, 最近在健身增肌"
    })
    if r and r.status_code == 201:
        data = r.json()
        ai_reply = data.get("content", "")[:80]
        PASS += 1
        print(f"  [通过] 10.2 AI 回复 -- {ai_reply}...")
    else:
        FAIL += 1
        print(f"  [失败] 10.2 AI 回复 -- status={r.status_code if r else 'error'}")
        if r:
            print(f"     {r.text[:200]}")

    # 10.3 获取对话历史
    r = _get(f"/chat/sessions/{CHAT_SESSION_ID}")
    if r and r.ok:
        data = r.json()
        msg_count = len(data.get("messages", []))
        if msg_count >= 2:
            PASS += 1
            print(f"  [通过] 10.3 对话历史 -- {msg_count} 条消息 (用户 + AI)")
        else:
            FAIL += 1
            print(f"  [失败] 10.3 对话历史 -- 仅 {msg_count} 条 (期望 >=2)")
    else:
        FAIL += 1
        print(f"  [失败] 10.3 对话历史 -- status={r.status_code if r else 'error'}")
else:
    SKIP += 2
    print("  [跳过] 10.2-10.3 跳过 -- 无对话 session")


# ====================================================================
# 第 11 幕 -- 数据持久化验证 (回读检查)
# ====================================================================
print("\n-- 第 11 幕: 数据持久化验证 --")

# 11.1 验证健康档案持久化
r = _get("/users/me/profile")
if r and r.ok:
    prof = r.json()
    hp = prof.get("health_profile", {})
    kcal_ok = hp.get("daily_kcal_target") == 2500
    activity_ok = hp.get("activity_level") == "moderate"
    height_ok = hp.get("height_cm") == 178
    weight_ok = hp.get("weight_kg") == 82

    if kcal_ok and activity_ok and height_ok and weight_ok:
        PASS += 1
        print(f"  [通过] 11.1 健康档案已持久化 -- 热量目标={hp.get('daily_kcal_target')}kcal, "
              f"活动={hp.get('activity_level')}, 身高={hp.get('height_cm')}cm, "
              f"体重={hp.get('weight_kg')}kg, BMI={hp.get('bmi')}")
    else:
        FAIL += 1
        print(f"  [失败] 11.1 健康档案不匹配 -- 热量目标={hp.get('daily_kcal_target')}(期望2500), "
              f"活动={hp.get('activity_level')}(期望moderate)")
else:
    FAIL += 1
    print(f"  [失败] 11.1 健康档案回读失败")

# 11.2 验证健康目标持久化
r = _get("/users/me/profile")
if r and r.ok:
    prof = r.json()
    goals = prof.get("health_goals", [])
    goal_types = [g["goal_type"] for g in goals]

    if "gain_muscle" in goal_types and "eye_health" in goal_types and "energy_boost" in goal_types:
        PASS += 1
        print(f"  [通过] 11.2 健康目标已持久化 -- {len(goals)} 个: {goal_types}")
    else:
        FAIL += 1
        print(f"  [失败] 11.2 健康目标不匹配 -- 实际: {goal_types}")
else:
    FAIL += 1
    print(f"  [失败] 11.2 健康目标回读失败")

# 11.3 验证偏好持久化
r = _get("/users/me/preferences")
if r and r.ok:
    prefs = r.json()
    if prefs.get("spice_level") == 3 and prefs.get("budget_per_meal") == 3500:
        PASS += 1
        print(f"  [通过] 11.3 偏好已持久化 -- 辣度={prefs.get('spice_level')}, "
              f"预算={prefs.get('budget_per_meal')}分, "
              f"黑名单={prefs.get('food_blacklist')}")
    else:
        FAIL += 1
        print(f"  [失败] 11.3 偏好不匹配 -- 辣度={prefs.get('spice_level')}(期望3), "
              f"预算={prefs.get('budget_per_meal')}(期望3500)")
else:
    FAIL += 1
    print(f"  [失败] 11.3 偏好回读失败")

# 11.4 验证位置持久化
r = _get("/location/current")
if r and r.ok:
    loc = r.json()
    has_loc = loc.get("latitude") is not None and loc.get("longitude") is not None
    has_city = bool(loc.get("city"))
    if has_loc or has_city:
        PASS += 1
        print(f"  [通过] 11.4 位置已持久化 -- 城市={loc.get('city')}, "
              f"纬度={loc.get('latitude')}, 经度={loc.get('longitude')}")
    else:
        FAIL += 1
        print(f"  [失败] 11.4 位置未持久化 -- 纬度={loc.get('latitude')}, 城市={loc.get('city')}")
else:
    FAIL += 1
    print(f"  [失败] 11.4 位置回读失败")

# 11.5 验证饮食记录持久化
r = _get("/food-logs?page_size=10")
if r and r.ok:
    data = r.json()
    log_count = len(data.get("items", []))
    if log_count >= 1:
        PASS += 1
        print(f"  [通过] 11.5 饮食记录已持久化 -- {log_count} 条")
    else:
        FAIL += 1
        print(f"  [失败] 11.5 饮食记录未持久化 -- 0 条")
else:
    FAIL += 1
    print(f"  [失败] 11.5 饮食记录回读失败 -- status={r.status_code if r else 'error'}")

# 11.6 验证过敏源持久化
r = _get("/users/me/profile")
if r and r.ok:
    prof = r.json()
    allergens = prof.get("allergens", [])
    allergen_names = [a["allergen"] for a in allergens]
    if "peanut" in allergen_names and "shrimp" in allergen_names:
        PASS += 1
        print(f"  [通过] 11.6 过敏源已持久化 -- {allergen_names}")
    else:
        FAIL += 1
        print(f"  [失败] 11.6 过敏源不匹配 -- 实际: {allergen_names}")
else:
    FAIL += 1
    print(f"  [失败] 11.6 过敏源回读失败")


# ====================================================================
# 最终报告
# ====================================================================
total = PASS + FAIL + SKIP
print("\n" + "=" * 60)
print(f"  产品验收测试结果")
print(f"  " + "-" * 28)
print(f"  [通过] PASS:  {PASS}")
print(f"  [失败] FAIL:  {FAIL}")
if SKIP:
    print(f"  [跳过] SKIP:  {SKIP}")
print(f"  总计:  {total} 项检查")
print(f"  " + "-" * 28)

if FAIL == 0:
    print(f"  结论:  验收通过 -- 所有检查通过, 产品可以发布。")
    exit_code = 0
else:
    print(f"  结论:  验收不通过 -- {FAIL} 项失败, 需要排查。")
    exit_code = 1

print("=" * 60)
print(f"  测试用户: {EMAIL}")
print(f"  时间戳:   {ts}")
print("=" * 60)

sys.exit(exit_code)
