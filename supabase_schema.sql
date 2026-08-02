-- ============================================================================
-- NutriAgent — Supabase PostgreSQL Schema
-- 数据库：Supabase PostgreSQL 15+ + pgvector
-- 版本：v2.0 (Supabase Compatible)
-- 日期：2026-08-02
--
-- 特点：
--   - 可以重复执行（幂等）
--   - IF NOT EXISTS 保护所有对象
--   - ENUM 用 DO $$ 块安全创建
--   - 兼容 Supabase / Railway / 本地 PostgreSQL
-- ============================================================================

-- ============================================================================
-- 0. 扩展
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================================
-- 1. 枚举类型（幂等 — 重复执行不报错）
-- ============================================================================

DO $$ BEGIN CREATE TYPE gender_enum AS ENUM ('male','female','other','prefer_not_to_say'); EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN CREATE TYPE activity_level_enum AS ENUM ('sedentary','light','moderate','active','very_active'); EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN CREATE TYPE diet_type_enum AS ENUM ('omnivore','vegetarian','vegan','keto','low_carb','paleo','mediterranean','dash','gluten_free','halal','custom'); EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN CREATE TYPE meal_type_enum AS ENUM ('breakfast','lunch','dinner','snack','late_night'); EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN CREATE TYPE goal_type_enum AS ENUM ('lose_weight','gain_muscle','maintain','blood_sugar','eye_health','hair_health','gut_health','energy_boost','anti_inflammatory','heart_health'); EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN CREATE TYPE severity_enum AS ENUM ('mild','moderate','severe'); EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN CREATE TYPE source_type_enum AS ENUM ('manual','photo','voice','delivery_order','ai_estimate'); EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN CREATE TYPE feedback_enum AS ENUM ('positive','negative','neutral','skip'); EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN CREATE TYPE memory_type_enum AS ENUM ('fact','preference','episode','summary','goal'); EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN CREATE TYPE recommend_status_enum AS ENUM ('generated','presented','accepted','rejected','expired'); EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN CREATE TYPE notification_channel_enum AS ENUM ('push','email','wechat','sms'); EXCEPTION WHEN duplicate_object THEN null; END $$;
DO $$ BEGIN CREATE TYPE food_category_enum AS ENUM ('staple','meat','poultry','seafood','egg','dairy','legume','vegetable','fruit','nut','oil','beverage','snack','condiment','supplement','mixed_dish','fast_food','other'); EXCEPTION WHEN duplicate_object THEN null; END $$;

-- ============================================================================
-- 2. 用户域
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone               VARCHAR(20)  UNIQUE,
    email               VARCHAR(255) UNIQUE,
    wechat_union_id     VARCHAR(64)  UNIQUE,
    wechat_open_id      VARCHAR(64)  UNIQUE,
    nickname            VARCHAR(64)  NOT NULL,
    avatar_url          VARCHAR(512),
    gender              gender_enum,
    password_hash       VARCHAR(255),
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    is_admin            BOOLEAN      NOT NULL DEFAULT FALSE,
    last_login_at       TIMESTAMPTZ,
    last_login_ip       INET,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS user_health_profiles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    gender              gender_enum,
    birth_date          DATE,
    height_cm           NUMERIC(5,1) CHECK (height_cm BETWEEN 50 AND 300),
    weight_kg           NUMERIC(5,1) CHECK (weight_kg BETWEEN 20 AND 500),
    bmi                 NUMERIC(4,1) GENERATED ALWAYS AS (
                            CASE WHEN height_cm > 0 AND weight_kg > 0
                            THEN ROUND((weight_kg / ((height_cm/100)^2))::numeric, 1)
                            ELSE NULL END
                        ) STORED,
    body_fat_pct        NUMERIC(4,1) CHECK (body_fat_pct BETWEEN 1 AND 70),
    muscle_mass_kg      NUMERIC(5,1),
    waist_cm            NUMERIC(5,1),
    bmr_kcal            INTEGER,
    daily_kcal_target   INTEGER CHECK (daily_kcal_target BETWEEN 800 AND 6000),
    target_protein_pct  NUMERIC(4,1) DEFAULT 20 CHECK (target_protein_pct BETWEEN 5 AND 60),
    target_fat_pct      NUMERIC(4,1) DEFAULT 30 CHECK (target_fat_pct BETWEEN 5 AND 70),
    target_carbs_pct    NUMERIC(4,1) DEFAULT 50 CHECK (target_carbs_pct BETWEEN 5 AND 80),
    activity_level      activity_level_enum DEFAULT 'sedentary',
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT chk_macro_sum CHECK (
        ABS(COALESCE(target_protein_pct,20) + COALESCE(target_fat_pct,30) + COALESCE(target_carbs_pct,50) - 100) < 1
    )
);

CREATE TABLE IF NOT EXISTS user_diet_types (
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    diet_type           diet_type_enum NOT NULL,
    is_primary          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, diet_type)
);

CREATE TABLE IF NOT EXISTS user_health_goals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    goal_type           goal_type_enum NOT NULL,
    priority            SMALLINT NOT NULL DEFAULT 0 CHECK (priority BETWEEN 0 AND 10),
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    target_description  TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, goal_type)
);

CREATE TABLE IF NOT EXISTS user_allergens (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    allergen            VARCHAR(100) NOT NULL,
    severity            severity_enum DEFAULT 'moderate',
    notes               TEXT,
    verified_by_doctor  BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, allergen)
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id             UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    spice_level         SMALLINT CHECK (spice_level BETWEEN 0 AND 5),
    sweet_level         SMALLINT CHECK (sweet_level BETWEEN 0 AND 5),
    oil_level           SMALLINT CHECK (oil_level BETWEEN 0 AND 5),
    budget_per_meal     INTEGER CHECK (budget_per_meal > 0),
    cuisine_prefs       JSONB DEFAULT '{}',
    food_blacklist      JSONB DEFAULT '[]',
    food_whitelist      JSONB DEFAULT '[]',
    cooking_prefs       JSONB DEFAULT '{}',
    meal_schedule       JSONB DEFAULT '{}',
    extra               JSONB DEFAULT '{}',
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_caffeine_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    log_date            DATE NOT NULL DEFAULT CURRENT_DATE,
    total_mg            INTEGER NOT NULL DEFAULT 0,
    drink_count         SMALLINT NOT NULL DEFAULT 0,
    target_limit_mg     INTEGER DEFAULT 400,
    over_limit          BOOLEAN GENERATED ALWAYS AS (total_mg > target_limit_mg) STORED,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, log_date)
);

-- ============================================================================
-- 3. 食物营养域
-- ============================================================================

CREATE TABLE IF NOT EXISTS food_categories (
    id                  SMALLINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    category            food_category_enum NOT NULL UNIQUE,
    parent_id           SMALLINT REFERENCES food_categories(id),
    name_zh             VARCHAR(64) NOT NULL,
    icon_emoji          VARCHAR(8),
    sort_order          SMALLINT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS foods (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id         SMALLINT NOT NULL REFERENCES food_categories(id),
    name_zh             VARCHAR(128) NOT NULL,
    name_en             VARCHAR(128),
    alias               TEXT[] DEFAULT '{}',
    thumb_url           VARCHAR(512),
    energy_kcal         NUMERIC(7,1) NOT NULL CHECK (energy_kcal >= 0),
    energy_kj           NUMERIC(7,1) GENERATED ALWAYS AS (energy_kcal * 4.184) STORED,
    protein_g           NUMERIC(6,1) DEFAULT 0 CHECK (protein_g >= 0),
    fat_g               NUMERIC(6,1) DEFAULT 0 CHECK (fat_g >= 0),
    carbs_g             NUMERIC(6,1) DEFAULT 0 CHECK (carbs_g >= 0),
    fiber_g             NUMERIC(6,1) DEFAULT 0 CHECK (fiber_g >= 0),
    sugar_g             NUMERIC(6,1) DEFAULT 0 CHECK (sugar_g >= 0),
    sodium_mg           NUMERIC(7,1) DEFAULT 0 CHECK (sodium_mg >= 0),
    cholesterol_mg      NUMERIC(6,1) DEFAULT 0 CHECK (cholesterol_mg >= 0),
    vitamin_a_ug        NUMERIC(7,1),
    vitamin_c_mg        NUMERIC(6,1),
    vitamin_e_mg        NUMERIC(6,1),
    lutein_ug           NUMERIC(7,1),
    omega3_g            NUMERIC(6,2),
    caffeine_mg         NUMERIC(6,1),
    calcium_mg          NUMERIC(7,1),
    iron_mg             NUMERIC(6,1),
    zinc_mg             NUMERIC(6,1),
    magnesium_mg        NUMERIC(7,1),
    glycemic_index      SMALLINT CHECK (glycemic_index BETWEEN 0 AND 150),
    edible_portion_pct  NUMERIC(4,1) DEFAULT 100,
    is_common           BOOLEAN DEFAULT FALSE,
    is_processed        BOOLEAN DEFAULT FALSE,
    data_source         VARCHAR(128) DEFAULT '中国食物成分表',
    embedding           VECTOR(1536),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS food_goal_tags (
    food_id             UUID NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
    goal_type           goal_type_enum NOT NULL,
    relevance           NUMERIC(3,2) DEFAULT 1.0 CHECK (relevance BETWEEN 0 AND 1),
    PRIMARY KEY (food_id, goal_type)
);

CREATE TABLE IF NOT EXISTS delivery_dishes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform            VARCHAR(32) NOT NULL,
    platform_dish_id    VARCHAR(128) NOT NULL,
    merchant_name       VARCHAR(256) NOT NULL,
    dish_name           VARCHAR(256) NOT NULL,
    price_cent          INTEGER NOT NULL,
    image_url           VARCHAR(512),
    merchant_address    VARCHAR(512),
    merchant_lat        NUMERIC(10,7),
    merchant_lng        NUMERIC(10,7),
    estimated_kcal      INTEGER,
    estimated_protein_g NUMERIC(5,1),
    estimated_fat_g     NUMERIC(5,1),
    estimated_carbs_g   NUMERIC(5,1),
    health_score        SMALLINT CHECK (health_score BETWEEN 0 AND 100),
    raw_data            JSONB,
    synced_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (platform, platform_dish_id)
);

-- ============================================================================
-- 4. 饮食记录域
-- ============================================================================

CREATE TABLE IF NOT EXISTS food_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    meal_type           meal_type_enum NOT NULL,
    meal_date           DATE NOT NULL DEFAULT CURRENT_DATE,
    meal_time           TIME NOT NULL DEFAULT CURRENT_TIME,
    source              source_type_enum DEFAULT 'manual',
    total_kcal          NUMERIC(7,1) DEFAULT 0,
    total_protein_g     NUMERIC(6,1) DEFAULT 0,
    total_fat_g         NUMERIC(6,1) DEFAULT 0,
    total_carbs_g       NUMERIC(6,1) DEFAULT 0,
    total_fiber_g       NUMERIC(6,1) DEFAULT 0,
    total_sodium_mg     NUMERIC(7,1) DEFAULT 0,
    total_caffeine_mg   NUMERIC(6,1) DEFAULT 0,
    mood_before         SMALLINT CHECK (mood_before BETWEEN 1 AND 5),
    mood_after          SMALLINT CHECK (mood_after BETWEEN 1 AND 5),
    satiety_level       SMALLINT CHECK (satiety_level BETWEEN 1 AND 5),
    notes               TEXT,
    photo_url           VARCHAR(512),
    location            VARCHAR(256),
    eaten_with          VARCHAR(256),
    cost_cent           INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS food_log_items (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    food_log_id         UUID NOT NULL REFERENCES food_logs(id) ON DELETE CASCADE,
    food_id             UUID REFERENCES foods(id),
    food_name           VARCHAR(256) NOT NULL,
    serving_size_g      NUMERIC(7,1) NOT NULL CHECK (serving_size_g > 0),
    serving_unit        VARCHAR(32) DEFAULT 'g',
    energy_kcal         NUMERIC(7,1) NOT NULL,
    protein_g           NUMERIC(6,1) DEFAULT 0,
    fat_g               NUMERIC(6,1) DEFAULT 0,
    carbs_g             NUMERIC(6,1) DEFAULT 0,
    fiber_g             NUMERIC(6,1) DEFAULT 0,
    sodium_mg           NUMERIC(7,1) DEFAULT 0,
    caffeine_mg         NUMERIC(6,1) DEFAULT 0,
    sort_order          SMALLINT DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS daily_nutrition_summary (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    summary_date        DATE NOT NULL,
    total_kcal          NUMERIC(7,1) DEFAULT 0,
    total_protein_g     NUMERIC(6,1) DEFAULT 0,
    total_fat_g         NUMERIC(6,1) DEFAULT 0,
    total_carbs_g       NUMERIC(6,1) DEFAULT 0,
    total_fiber_g       NUMERIC(6,1) DEFAULT 0,
    total_sodium_mg     NUMERIC(7,1) DEFAULT 0,
    total_caffeine_mg   NUMERIC(6,1) DEFAULT 0,
    kcal_target         INTEGER,
    kcal_achievement_pct NUMERIC(5,1),
    meal_count          SMALLINT DEFAULT 0,
    nutrition_score     SMALLINT CHECK (nutrition_score BETWEEN 0 AND 100),
    score_feedback      TEXT,
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, summary_date)
);

-- ============================================================================
-- 5. Agent 记忆域
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_memories (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    memory_type         memory_type_enum NOT NULL,
    title               VARCHAR(256) NOT NULL,
    content             TEXT NOT NULL,
    key_facts           JSONB DEFAULT '[]',
    importance          NUMERIC(3,2) NOT NULL DEFAULT 0.5 CHECK (importance BETWEEN 0 AND 1),
    access_count        INTEGER NOT NULL DEFAULT 0,
    last_accessed_at    TIMESTAMPTZ,
    decay_factor        NUMERIC(4,3) DEFAULT 1.0,
    source              VARCHAR(64) DEFAULT 'conversation',
    source_id           UUID,
    confidence          NUMERIC(3,2) DEFAULT 1.0 CHECK (confidence BETWEEN 0 AND 1),
    embedding           VECTOR(1536),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at          TIMESTAMPTZ,
    CONSTRAINT chk_valid_decay CHECK (decay_factor BETWEEN 0 AND 1)
);

CREATE TABLE IF NOT EXISTS agent_memory_links (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_memory_id    UUID NOT NULL REFERENCES agent_memories(id) ON DELETE CASCADE,
    target_memory_id    UUID NOT NULL REFERENCES agent_memories(id) ON DELETE CASCADE,
    relation            VARCHAR(128) NOT NULL,
    weight              NUMERIC(3,2) DEFAULT 1.0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_memory_id, target_memory_id, relation),
    CHECK (source_memory_id <> target_memory_id)
);

CREATE TABLE IF NOT EXISTS agent_preference_signals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    food_id             UUID REFERENCES foods(id),
    food_name           VARCHAR(256),
    signal_type         VARCHAR(32) NOT NULL,
    signal_strength     NUMERIC(3,2) DEFAULT 0.7 CHECK (signal_strength BETWEEN 0 AND 1),
    signal_source       VARCHAR(64),
    context             JSONB,
    occurrence_count    INTEGER DEFAULT 1,
    last_signal_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- 6. 推荐引擎域
-- ============================================================================

CREATE TABLE IF NOT EXISTS recommendation_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recommend_type      VARCHAR(32) NOT NULL,
    scenario            VARCHAR(64),
    meal_type           meal_type_enum,
    target_date         DATE,
    model_name          VARCHAR(64) NOT NULL,
    model_version       VARCHAR(32),
    prompt_template_id  VARCHAR(64),
    retrieval_sources   JSONB,
    recommendation_json JSONB NOT NULL,
    summary_text        TEXT NOT NULL,
    prompt_tokens       INTEGER,
    completion_tokens   INTEGER,
    total_tokens        INTEGER,
    latency_ms          INTEGER,
    status              recommend_status_enum DEFAULT 'generated',
    presented_at        TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ,
    feedback            feedback_enum,
    feedback_detail     TEXT,
    feedback_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS recommendation_items (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id   UUID NOT NULL REFERENCES recommendation_logs(id) ON DELETE CASCADE,
    item_type           VARCHAR(32) NOT NULL DEFAULT 'food',
    food_name           VARCHAR(256) NOT NULL,
    food_id             UUID REFERENCES foods(id),
    delivery_dish_id    UUID REFERENCES delivery_dishes(id),
    serving_size_g      NUMERIC(7,1),
    estimated_kcal      NUMERIC(7,1),
    estimated_protein_g NUMERIC(6,1),
    estimated_fat_g     NUMERIC(6,1),
    estimated_carbs_g   NUMERIC(6,1),
    reason_text         TEXT,
    nutrition_tags      TEXT[] DEFAULT '{}',
    sort_order          SMALLINT DEFAULT 0,
    item_feedback       feedback_enum,
    was_consumed        BOOLEAN,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS meal_plans (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_week_start     DATE NOT NULL,
    plan_name           VARCHAR(256),
    status              VARCHAR(32) DEFAULT 'active',
    daily_kcal_target   INTEGER,
    daily_protein_g     NUMERIC(6,1),
    daily_fat_g         NUMERIC(6,1),
    daily_carbs_g       NUMERIC(6,1),
    source_recommendation_id UUID REFERENCES recommendation_logs(id),
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, plan_week_start)
);

CREATE TABLE IF NOT EXISTS meal_plan_items (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meal_plan_id        UUID NOT NULL REFERENCES meal_plans(id) ON DELETE CASCADE,
    plan_date           DATE NOT NULL,
    meal_type           meal_type_enum NOT NULL,
    food_name           VARCHAR(256) NOT NULL,
    food_id             UUID REFERENCES foods(id),
    serving_size_g      NUMERIC(7,1),
    estimated_kcal      NUMERIC(7,1),
    is_completed        BOOLEAN DEFAULT FALSE,
    actual_food_log_id  UUID REFERENCES food_logs(id),
    sort_order          SMALLINT DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- 7. 系统辅助表
-- ============================================================================

CREATE TABLE IF NOT EXISTS prompt_templates (
    id                  VARCHAR(64) PRIMARY KEY,
    version             INTEGER NOT NULL DEFAULT 1,
    name                VARCHAR(128) NOT NULL,
    description         TEXT,
    system_prompt       TEXT NOT NULL,
    user_prompt_template TEXT NOT NULL,
    variables           JSONB DEFAULT '[]',
    model_preference    VARCHAR(64),
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS notifications (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel             notification_channel_enum NOT NULL,
    title               VARCHAR(256) NOT NULL,
    body                TEXT NOT NULL,
    action_url          VARCHAR(512),
    is_read             BOOLEAN DEFAULT FALSE,
    sent_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    read_at             TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_type        VARCHAR(32) DEFAULT 'chat',
    title               VARCHAR(256),
    is_active           BOOLEAN DEFAULT TRUE,
    context_json        JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role                VARCHAR(16) NOT NULL CHECK (role IN ('user','assistant','system')),
    content             TEXT NOT NULL,
    metadata_json       JSONB DEFAULT '{}',
    embedding           VECTOR(1536),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- 8. 索引（幂等）
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_users_phone               ON users(phone)             WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_users_wechat_union_id     ON users(wechat_union_id)   WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_users_created_at          ON users(created_at);
CREATE INDEX IF NOT EXISTS idx_user_health_profiles_user ON user_health_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_allergens_user       ON user_allergens(user_id);
CREATE INDEX IF NOT EXISTS idx_user_health_goals_user    ON user_health_goals(user_id) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_user_diet_types_user      ON user_diet_types(user_id);
CREATE INDEX IF NOT EXISTS idx_food_logs_user_date       ON food_logs(user_id, meal_date DESC);
CREATE INDEX IF NOT EXISTS idx_food_logs_user_meal       ON food_logs(user_id, meal_date, meal_type);
CREATE INDEX IF NOT EXISTS idx_food_logs_date            ON food_logs(meal_date);
CREATE INDEX IF NOT EXISTS idx_food_log_items_log        ON food_log_items(food_log_id);
CREATE INDEX IF NOT EXISTS idx_food_log_items_food       ON food_log_items(food_id);
CREATE INDEX IF NOT EXISTS idx_daily_summary_user_date   ON daily_nutrition_summary(user_id, summary_date DESC);
CREATE INDEX IF NOT EXISTS idx_foods_category            ON foods(category_id);
CREATE INDEX IF NOT EXISTS idx_foods_name_zh             ON foods USING gin(name_zh gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_foods_embedding           ON foods USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_foods_is_common           ON foods(is_common) WHERE is_common = TRUE;
CREATE INDEX IF NOT EXISTS idx_delivery_dishes_platform  ON delivery_dishes(platform, platform_dish_id);
CREATE INDEX IF NOT EXISTS idx_delivery_dishes_location  ON delivery_dishes(merchant_lat, merchant_lng);
CREATE INDEX IF NOT EXISTS idx_agent_memories_user       ON agent_memories(user_id, memory_type);
CREATE INDEX IF NOT EXISTS idx_agent_memories_importance ON agent_memories(user_id, importance DESC);
CREATE INDEX IF NOT EXISTS idx_agent_memories_embedding  ON agent_memories USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
CREATE INDEX IF NOT EXISTS idx_agent_memories_expires    ON agent_memories(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_agent_memory_links_src    ON agent_memory_links(source_memory_id);
CREATE INDEX IF NOT EXISTS idx_agent_memory_links_tgt    ON agent_memory_links(target_memory_id);
CREATE INDEX IF NOT EXISTS idx_agent_signals_user        ON agent_preference_signals(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_signals_food        ON agent_preference_signals(user_id, food_id);
CREATE INDEX IF NOT EXISTS idx_recommendation_logs_user  ON recommendation_logs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recommendation_logs_date  ON recommendation_logs(user_id, target_date);
CREATE INDEX IF NOT EXISTS idx_recommendation_logs_fb    ON recommendation_logs(user_id, feedback) WHERE feedback IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_recommendation_items_rec  ON recommendation_items(recommendation_id);
CREATE INDEX IF NOT EXISTS idx_meal_plans_user_week      ON meal_plans(user_id, plan_week_start DESC);
CREATE INDEX IF NOT EXISTS idx_meal_plan_items_plan      ON meal_plan_items(meal_plan_id, plan_date, meal_type);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user        ON chat_sessions(user_id, updated_at DESC) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_chat_messages_session     ON chat_messages(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_notifications_user        ON notifications(user_id, sent_at DESC) WHERE is_read = FALSE;

-- ============================================================================
-- 9. 函数 + 触发器（幂等）
-- ============================================================================

CREATE OR REPLACE FUNCTION update_food_log_totals()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        UPDATE food_logs
        SET total_kcal        = COALESCE((SELECT SUM(energy_kcal)     FROM food_log_items WHERE food_log_id = OLD.food_log_id), 0),
            total_protein_g   = COALESCE((SELECT SUM(protein_g)       FROM food_log_items WHERE food_log_id = OLD.food_log_id), 0),
            total_fat_g       = COALESCE((SELECT SUM(fat_g)           FROM food_log_items WHERE food_log_id = OLD.food_log_id), 0),
            total_carbs_g     = COALESCE((SELECT SUM(carbs_g)         FROM food_log_items WHERE food_log_id = OLD.food_log_id), 0),
            total_fiber_g     = COALESCE((SELECT SUM(fiber_g)         FROM food_log_items WHERE food_log_id = OLD.food_log_id), 0),
            total_sodium_mg   = COALESCE((SELECT SUM(sodium_mg)       FROM food_log_items WHERE food_log_id = OLD.food_log_id), 0),
            total_caffeine_mg = COALESCE((SELECT SUM(caffeine_mg)     FROM food_log_items WHERE food_log_id = OLD.food_log_id), 0),
            updated_at        = now()
        WHERE id = OLD.food_log_id;
        RETURN OLD;
    ELSE
        UPDATE food_logs
        SET total_kcal        = COALESCE((SELECT SUM(energy_kcal)     FROM food_log_items WHERE food_log_id = NEW.food_log_id), 0),
            total_protein_g   = COALESCE((SELECT SUM(protein_g)       FROM food_log_items WHERE food_log_id = NEW.food_log_id), 0),
            total_fat_g       = COALESCE((SELECT SUM(fat_g)           FROM food_log_items WHERE food_log_id = NEW.food_log_id), 0),
            total_carbs_g     = COALESCE((SELECT SUM(carbs_g)         FROM food_log_items WHERE food_log_id = NEW.food_log_id), 0),
            total_fiber_g     = COALESCE((SELECT SUM(fiber_g)         FROM food_log_items WHERE food_log_id = NEW.food_log_id), 0),
            total_sodium_mg   = COALESCE((SELECT SUM(sodium_mg)       FROM food_log_items WHERE food_log_id = NEW.food_log_id), 0),
            total_caffeine_mg = COALESCE((SELECT SUM(caffeine_mg)     FROM food_log_items WHERE food_log_id = NEW.food_log_id), 0),
            updated_at        = now()
        WHERE id = NEW.food_log_id;
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_food_log_items_totals ON food_log_items;
CREATE TRIGGER trg_food_log_items_totals
    AFTER INSERT OR UPDATE OR DELETE ON food_log_items
    FOR EACH ROW EXECUTE FUNCTION update_food_log_totals();

CREATE OR REPLACE FUNCTION calc_bmr()
RETURNS TRIGGER AS $$
DECLARE
    age_years INTEGER;
BEGIN
    IF NEW.weight_kg > 0 AND NEW.height_cm > 0 AND NEW.birth_date IS NOT NULL THEN
        age_years := EXTRACT(YEAR FROM age(NEW.birth_date));
        IF NEW.gender = 'male' THEN
            NEW.bmr_kcal := ROUND(10 * NEW.weight_kg + 6.25 * NEW.height_cm - 5 * age_years + 5);
        ELSIF NEW.gender = 'female' THEN
            NEW.bmr_kcal := ROUND(10 * NEW.weight_kg + 6.25 * NEW.height_cm - 5 * age_years - 161);
        ELSE
            NEW.bmr_kcal := ROUND(10 * NEW.weight_kg + 6.25 * NEW.height_cm - 5 * age_years);
        END IF;
    ELSE
        NEW.bmr_kcal := NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_bmr_calc ON user_health_profiles;
CREATE TRIGGER trg_bmr_calc
    BEFORE INSERT OR UPDATE OF gender, weight_kg, height_cm, birth_date ON user_health_profiles
    FOR EACH ROW EXECUTE FUNCTION calc_bmr();

CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_timestamp();

DROP TRIGGER IF EXISTS trg_food_logs_updated_at ON food_logs;
CREATE TRIGGER trg_food_logs_updated_at BEFORE UPDATE ON food_logs FOR EACH ROW EXECUTE FUNCTION update_timestamp();

DROP TRIGGER IF EXISTS trg_foods_updated_at ON foods;
CREATE TRIGGER trg_foods_updated_at BEFORE UPDATE ON foods FOR EACH ROW EXECUTE FUNCTION update_timestamp();

DROP TRIGGER IF EXISTS trg_agent_memories_updated_at ON agent_memories;
CREATE TRIGGER trg_agent_memories_updated_at BEFORE UPDATE ON agent_memories FOR EACH ROW EXECUTE FUNCTION update_timestamp();

DROP TRIGGER IF EXISTS trg_recommendation_updated_at ON recommendation_logs;
CREATE TRIGGER trg_recommendation_updated_at BEFORE UPDATE ON recommendation_logs FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- ============================================================================
-- 10. 初始数据（幂等）
-- ============================================================================

INSERT INTO food_categories (category, name_zh, icon_emoji, sort_order) VALUES
    ('staple','主食','🍚',1),('meat','畜肉','🥩',2),('poultry','禽肉','🍗',3),
    ('seafood','水产','🐟',4),('egg','蛋类','🥚',5),('dairy','奶制品','🥛',6),
    ('legume','豆类','🫘',7),('vegetable','蔬菜','🥬',8),('fruit','水果','🍎',9),
    ('nut','坚果种子','🥜',10),('oil','油脂','🫒',11),('beverage','饮料','🥤',12),
    ('snack','零食','🍪',13),('condiment','调味品','🧂',14),('supplement','补剂','💊',15),
    ('mixed_dish','混合菜肴','🍲',16),('fast_food','快餐','🍔',17),('other','其他','📦',99)
ON CONFLICT (category) DO NOTHING;
