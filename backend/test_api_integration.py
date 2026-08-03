"""
NutriAgent — API Integration Test Suite
Run: python test_api_integration.py
"""

import requests, json, time, sys

BASE = "https://nutriagent-backend.vercel.app/api/v1"
HEADERS = {"Content-Type": "application/json"}
TOKEN = None
UID = None

PASS = 0
FAIL = 0
WARN = 0

def t(method, path, body=None, expect=200, auth=True, name=""):
    global PASS, FAIL, WARN, TOKEN
    url = f"{BASE}{path}"
    h = dict(HEADERS)
    if auth and TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    try:
        start = time.time()
        r = requests.request(method, url, json=body, headers=h, timeout=30)
        elapsed = round((time.time() - start) * 1000)
        status = r.status_code

        if status == expect or (expect is None and status < 500):
            PASS += 1
            detail = ""
            try: detail = json.dumps(r.json(), ensure_ascii=False)[:120]
            except: detail = r.text[:120]
            print(f"  ✅ {name} ({status}ms)")
        elif status in (401, 403) and expect is None:
            WARN += 1
            print(f"  ⚠️ {name} → {status} (auth)")
        else:
            FAIL += 1
            detail = r.text[:200]
            print(f"  ❌ {name} → {status} expected {expect}")
            if status >= 400:
                print(f"     {detail}")
        return r
    except Exception as e:
        FAIL += 1
        print(f"  ❌ {name} → ERROR: {e}")
        return None

print("=" * 56)
print("  NutriAgent API Integration Test")
print("=" * 56)

# ================================================================
# 0. Auth — register + login
# ================================================================
print("\n── 0. Auth ──")
email = f"test{int(time.time())}@nutriagent.com"
r = t("POST", "/auth/register", {"nickname":"APITest","email":email,"password":"test123456"}, 201, False, "Register")
r = t("POST", "/auth/login", {"email":email,"password":"test123456"}, 200, False, "Login")
if r and r.ok:
    TOKEN = r.json()["access_token"]
    print(f"     Token acquired: {TOKEN[:20]}...")

r = t("POST", "/auth/login", {"email":email,"password":"wrong"}, 401, False, "Login (wrong pw)")
t("GET", "/users/me", expect=None, name="GET /users/me (no auth)", auth=False)

# ================================================================
# 1. User Profile
# ================================================================
print("\n── 1. User ──")
r = t("GET", "/users/me", name="GET /users/me")
if r and r.ok:
    data = r.json()
    UID = data.get("id")
    print(f"     User: {data.get('nickname')} ({data.get('email')})")
t("GET", "/users/me/profile", name="GET /users/me/profile")
t("PATCH", "/users/me/health-profile", {"height_cm":175,"weight_kg":70,"daily_kcal_target":2200}, 200, "PATCH health-profile")
t("GET", "/users/me/preferences", name="GET /users/me/preferences")

# ================================================================
# 2. Food Logs + Parse
# ================================================================
print("\n── 2. Food ──")
t("GET", "/food-logs?page_size=3", name="GET /food-logs")
t("POST", "/food-logs", {
    "meal_type":"breakfast","source":"manual",
    "items":[{"food_name":"Test Food","serving_size_g":200,"energy_kcal":300,"protein_g":20,"fat_g":10,"carbs_g":25,"fiber_g":3,"sodium_mg":100,"caffeine_mg":0,"sort_order":0}]
}, 201, "POST /food-logs")

# FoodParserAgent test
print("\n     [FoodParserAgent]")
r = t("POST", "/food-logs/parse", {"text":"早餐吃两个鸡蛋一杯牛奶"}, 200, True, "Parse '早餐吃两个鸡蛋...'")
if r and r.ok:
    data = r.json()
    items = data.get("items",[])
    for item in items:
        qty = f"x{item.get('quantity','?')}{item.get('unit','?')}"
        src = item.get("source","?")
        conf = item.get("confidence",0)
        kcal = item.get("energy_kcal",0)
        weight = item.get("serving_size_g",0)
        ok = (conf >= 0.5 and weight > 0 and kcal > 0)
        status = "✅" if ok else "⚠️"
        print(f"     {status} {item.get('food_name','?')} {qty} {weight}g {kcal}kcal conf={conf} src={src}")
    if not items:
        print("     ❌ No items parsed")
        FAIL += 1

# ================================================================
# 3. Recommendation
# ================================================================
print("\n── 3. Recommendation ──")
r = t("POST", "/recommendations/next-meal", {
    "daily_kcal_target":2200,"target_protein_pct":25,"target_fat_pct":30,"target_carbs_pct":45,
    "activity_level":"sedentary",
}, 200, "POST /recommendations/next-meal")
if r and r.ok:
    data = r.json()
    n_items = len(data.get("items",[]))
    n_restaurants = len(data.get("nearby_restaurants",[]))
    score = data.get("goal_alignment_score",0)
    print(f"     Items: {n_items}, Nearby: {n_restaurants}, Score: {score}")
    if n_items == 0:
        print("     ⚠️ No recommended items")

# ================================================================
# 4. Location
# ================================================================
print("\n── 4. Location ──")
t("GET", "/location/current", name="GET /location/current")
t("POST", "/location/update", {"latitude":31.23,"longitude":121.47}, 200, "POST /location/update")
t("POST", "/location/manual", {"city":"杭州","province":"浙江省","adcode":"330100"}, 200, "POST /location/manual")

# ================================================================
# 5. Restaurants
# ================================================================
print("\n── 5. Restaurants ──")
t("GET", "/restaurants/nearby?latitude=31.23&longitude=121.47&radius=3000", name="GET /restaurants/nearby")

# ================================================================
# 6. Chat
# ================================================================
print("\n── 6. Chat ──")
r = t("POST", "/chat/sessions", {"session_type":"chat"}, 201, "POST /chat/sessions")
sid = None
if r and r.ok:
    sid = r.json().get("id")
if sid:
    t("POST", f"/chat/sessions/{sid}/messages", {"content":"我不吃香菜"}, 201, "POST /chat/messages")

# ================================================================
# 7. Nutrition
# ================================================================
print("\n── 7. Nutrition ──")
t("GET", "/nutrition/dashboard", name="GET /nutrition/dashboard")
t("GET", "/nutrition/report/weekly?week_start=2026-07-27", name="GET /nutrition/report/weekly")

# ================================================================
# 8. Debug
# ================================================================
print("\n── 8. Debug ──")
t("GET", "/debug/agent-traces", name="GET /debug/agent-traces")
t("GET", "/health", name="GET /health", expect=None, auth=False)

# ================================================================
# REPORT
# ================================================================
total = PASS + FAIL + WARN
print("\n" + "=" * 56)
print(f"  RESULT: {PASS} PASS | {WARN} WARN | {FAIL} FAIL")
print(f"  Total: {total} tests")
if FAIL == 0:
    print("  STATUS: ✅ PRODUCTION READY")
else:
    print(f"  STATUS: ❌ {FAIL} FAILURES TO FIX")
print("=" * 56)
