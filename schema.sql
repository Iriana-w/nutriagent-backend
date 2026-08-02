-- ============================================================================
-- NutriAgent — 完整数据库 Schema
-- 数据库：PostgreSQL 16 + pgvector
-- 版本：v1.0
-- 日期：2026-07-30
-- ============================================================================

-- 扩展
-- 注意：uuid-ossp 在某些环境中不可用（云数据库/精简镜像），
-- 统一使用 pgcrypto 的 gen_random_uuid() 替代
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";              -- pgvector，用于 RAG 向量检索
CREATE EXTENSION IF NOT EXISTS "pg_trgm";             -- 三元组模糊搜索，用于 foods.name_zh GIN 索引

-- ============================================================================
-- 1. 枚举类型
-- ============================================================================

CREATE TYPE gender_enum          AS ENUM ('male', 'female', 'other', 'prefer_not_to_say');
CREATE TYPE activity_level_enum  AS ENUM ('sedentary', 'light', 'moderate', 'active', 'very_active');
CREATE TYPE diet_type_enum       AS ENUM (
    'omnivore',          -- 杂食
    'vegetarian',        -- 素食（蛋奶）
    'vegan',             -- 纯素
    'keto',              -- 生酮
    'low_carb',          -- 低碳水
    'paleo',             -- 原始饮食
    'mediterranean',     -- 地中海饮食
    'dash',              -- DASH 饮食（控血压）
    'gluten_free',       -- 无麸质
    'halal',             -- 清真
    'custom'             -- 自定义
);
CREATE TYPE meal_type_enum       AS ENUM ('breakfast', 'lunch', 'dinner', 'snack', 'late_night');
CREATE TYPE goal_type_enum       AS ENUM (
    'lose_weight',       -- 减脂
    'gain_muscle',       -- 增肌
    'maintain',          -- 维持体重
    'blood_sugar',       -- 控糖
    'eye_health',        -- 护眼
    'hair_health',       -- 护发
    'gut_health',        -- 肠胃调理
    'energy_boost',      -- 提升精力
    'anti_inflammatory', -- 抗炎
    'heart_health'       -- 心血管健康
);
CREATE TYPE severity_enum        AS ENUM ('mild', 'moderate', 'severe');
CREATE TYPE source_type_enum     AS ENUM ('manual', 'photo', 'voice', 'delivery_order', 'ai_estimate');
CREATE TYPE feedback_enum        AS ENUM ('positive', 'negative', 'neutral', 'skip');
CREATE TYPE memory_type_enum     AS ENUM ('fact', 'preference', 'episode', 'summary', 'goal');
CREATE TYPE recommend_status_enum AS ENUM ('generated', 'presented', 'accepted', 'rejected', 'expired');
CREATE TYPE notification_channel_enum AS ENUM ('push', 'email', 'wechat', 'sms');
CREATE TYPE food_category_enum   AS ENUM (
    'staple',            -- 主食
    'meat',              -- 肉类
    'poultry',           -- 禽肉
    'seafood',           -- 水产
    'egg',               -- 蛋类
    'dairy',             -- 奶制品
    'legume',            -- 豆类
    'vegetable',         -- 蔬菜
    'fruit',             -- 水果
    'nut',               -- 坚果种子
    'oil',               -- 油脂
    'beverage',          -- 饮料
    'snack',             -- 零食
    'condiment',         -- 调味品
    'supplement',        -- 补剂
    'mixed_dish',        -- 混合菜肴
    'fast_food',         -- 快餐
    'other'
);

-- ============================================================================
-- 2. 用户域
-- ============================================================================

-- 2.1 用户主表
-- 设计原因：只保留认证与身份字段；体测数据（身高/体重/出生日期）移至 user_health_profiles，
-- 因为 BMI/BMR 生成列需要与体测数据同表才能通过 GENERATED ALWAYS AS 计算
CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone               VARCHAR(20)  UNIQUE,                        -- 手机号（可选绑定）
    email               VARCHAR(255) UNIQUE,                        -- 邮箱（可选绑定）
    wechat_union_id     VARCHAR(64)  UNIQUE,                        -- 微信 UnionID
    wechat_open_id      VARCHAR(64)  UNIQUE,                        -- 微信公众号 OpenID
    nickname            VARCHAR(64)  NOT NULL,
    avatar_url          VARCHAR(512),
    gender              gender_enum,

    -- 认证
    password_hash       VARCHAR(255),                               -- bcrypt hash，微信登录用户可为空
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    is_admin            BOOLEAN      NOT NULL DEFAULT FALSE,
    last_login_at       TIMESTAMPTZ,
    last_login_ip       INET,

    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ                               -- 软删除
);

-- 2.2 用户健康画像（1:1 users）
-- 设计原因：所有体测 + 代谢数据集中于此表，使 BMI/BMR 生成列可以引用同表字段计算；
-- 1:1 关联 users，user_id 即唯一键
CREATE TABLE user_health_profiles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID         NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,

    -- 基础体征（生成列 BMI/BMR 的输入源，必须与生成列同表）
    gender              gender_enum,
    birth_date          DATE,                                           -- 用于计算年龄和 BMR
    height_cm           NUMERIC(5,1) CHECK (height_cm BETWEEN 50 AND 300),
    weight_kg           NUMERIC(5,1) CHECK (weight_kg BETWEEN 20 AND 500),

    -- 体成分
    bmi                 NUMERIC(4,1) GENERATED ALWAYS AS (
                            CASE WHEN height_cm > 0 AND weight_kg > 0
                            THEN ROUND((weight_kg / ((height_cm/100)^2))::numeric, 1)
                            ELSE NULL END
                        ) STORED,
    body_fat_pct        NUMERIC(4,1) CHECK (body_fat_pct BETWEEN 1 AND 70),
    muscle_mass_kg      NUMERIC(5,1),
    waist_cm            NUMERIC(5,1),

    -- 基础代谢（Mifflin-St Jeor 公式）
    -- 注意：不能使用 GENERATED ALWAYS，因为 age() 是 STABLE 函数（依赖当前日期）而非 IMMUTABLE；
    -- 改为触发器 trg_bmr_calc 在 INSERT/UPDATE 时自动计算
    bmr_kcal            INTEGER,

    -- 每日目标热量（可由用户手动覆盖计算值）
    daily_kcal_target   INTEGER      CHECK (daily_kcal_target BETWEEN 800 AND 6000),

    -- 宏量营养素目标占比（百分比，总和应为 100）
    target_protein_pct  NUMERIC(4,1) DEFAULT 20 CHECK (target_protein_pct BETWEEN 5 AND 60),
    target_fat_pct      NUMERIC(4,1) DEFAULT 30 CHECK (target_fat_pct BETWEEN 5 AND 70),
    target_carbs_pct    NUMERIC(4,1) DEFAULT 50 CHECK (target_carbs_pct BETWEEN 5 AND 80),

    -- 活动水平
    activity_level      activity_level_enum DEFAULT 'sedentary',

    -- 元数据
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    -- CHECK 约束：营养素之和约等于 100
    CONSTRAINT chk_macro_sum CHECK (
        ABS(COALESCE(target_protein_pct,20) + COALESCE(target_fat_pct,30) + COALESCE(target_carbs_pct,50) - 100) < 1
    )
);

-- 2.3 用户饮食类型（多对多：一个用户可同时有多种饮食偏好组合）
CREATE TABLE user_diet_types (
    user_id             UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    diet_type           diet_type_enum NOT NULL,
    is_primary          BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, diet_type)
);

-- 2.4 用户健康目标（多对多）
CREATE TABLE user_health_goals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    goal_type           goal_type_enum NOT NULL,
    priority            SMALLINT     NOT NULL DEFAULT 0 CHECK (priority BETWEEN 0 AND 10),
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    target_description  TEXT,                                         -- AI 可读的目标描述
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (user_id, goal_type)
);

-- 2.5 用户过敏源/忌口
CREATE TABLE user_allergens (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    allergen            VARCHAR(100) NOT NULL,                       -- 如 "peanut", "shrimp", "gluten"
    severity            severity_enum DEFAULT 'moderate',
    notes               TEXT,
    verified_by_doctor  BOOLEAN      DEFAULT FALSE,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (user_id, allergen)
);

-- 2.6 用户偏好标签（JSONB 灵活存储口味/禁忌等动态属性）
-- 设计原因：偏好维度多变（辣度、甜度、温度偏好、菜系偏好等），JSONB 避免频繁 DDL
CREATE TABLE user_preferences (
    user_id             UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,

    -- 结构化高频字段
    spice_level         SMALLINT     CHECK (spice_level BETWEEN 0 AND 5),  -- 辣度 0-5
    sweet_level         SMALLINT     CHECK (sweet_level BETWEEN 0 AND 5),
    oil_level           SMALLINT     CHECK (oil_level BETWEEN 0 AND 5),    -- 油腻接受度
    budget_per_meal     INTEGER      CHECK (budget_per_meal > 0),          -- 每餐预算（分）

    -- 动态扩展字段
    cuisine_prefs       JSONB        DEFAULT '{}',                         -- 菜系偏好 {"川菜":0.8, "日料":0.6}
    food_blacklist      JSONB        DEFAULT '[]',                         -- 黑名单食物 ["榴莲","苦瓜"]
    food_whitelist      JSONB        DEFAULT '[]',                         -- 偏爱食物 ["牛油果","三文鱼"]
    cooking_prefs       JSONB        DEFAULT '{}',                         -- 烹饪方式偏好 {"蒸":1, "煮":1, "炸":-1}
    meal_schedule       JSONB        DEFAULT '{}',                         -- 惯常用餐时间 {"breakfast":"08:30","lunch":"12:00"}
    extra               JSONB        DEFAULT '{}',                         -- 预留扩展

    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 2.7 用户咖啡因追踪
CREATE TABLE user_caffeine_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    log_date            DATE         NOT NULL DEFAULT CURRENT_DATE,
    total_mg            INTEGER      NOT NULL DEFAULT 0,                   -- 当日咖啡因总量(mg)
    drink_count         SMALLINT     NOT NULL DEFAULT 0,
    target_limit_mg     INTEGER      DEFAULT 400,                          -- 当日上限（默认400mg≈2杯）
    over_limit          BOOLEAN      GENERATED ALWAYS AS (total_mg > target_limit_mg) STORED,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (user_id, log_date)
);

-- ============================================================================
-- 3. 食物营养域（参考数据）
-- ============================================================================

-- 3.1 食物分类表
CREATE TABLE food_categories (
    id                  SMALLINT     PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    category            food_category_enum NOT NULL UNIQUE,
    parent_id           SMALLINT     REFERENCES food_categories(id),
    name_zh             VARCHAR(64)  NOT NULL,
    icon_emoji          VARCHAR(8),
    sort_order          SMALLINT     DEFAULT 0
);

-- 3.2 食物营养主表
-- 设计原因：以每 100g 可食部为基准存储，前端查询时按实际份量换算
CREATE TABLE foods (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id         SMALLINT     NOT NULL REFERENCES food_categories(id),

    -- 基本信息
    name_zh             VARCHAR(128) NOT NULL,                             -- 中文名称
    name_en             VARCHAR(128),                                      -- 英文名称
    alias               TEXT[]       DEFAULT '{}',                         -- 别名数组（如 土豆/马铃薯/洋芋）
    thumb_url           VARCHAR(512),

    -- 每 100g 可食部营养成分
    energy_kcal         NUMERIC(7,1) NOT NULL CHECK (energy_kcal >= 0),   -- 热量 kcal
    energy_kj           NUMERIC(7,1) GENERATED ALWAYS AS (energy_kcal * 4.184) STORED,
    protein_g           NUMERIC(6,1) DEFAULT 0 CHECK (protein_g >= 0),
    fat_g               NUMERIC(6,1) DEFAULT 0 CHECK (fat_g >= 0),
    carbs_g             NUMERIC(6,1) DEFAULT 0 CHECK (carbs_g >= 0),
    fiber_g             NUMERIC(6,1) DEFAULT 0 CHECK (fiber_g >= 0),
    sugar_g             NUMERIC(6,1) DEFAULT 0 CHECK (sugar_g >= 0),
    sodium_mg           NUMERIC(7,1) DEFAULT 0 CHECK (sodium_mg >= 0),
    cholesterol_mg      NUMERIC(6,1) DEFAULT 0 CHECK (cholesterol_mg >= 0),

    -- 关键微量元素（程序员健康重点关注）
    vitamin_a_ug        NUMERIC(7,1),
    vitamin_c_mg        NUMERIC(6,1),
    vitamin_e_mg        NUMERIC(6,1),
    lutein_ug           NUMERIC(7,1),                                     -- 叶黄素（护眼）
    omega3_g            NUMERIC(6,2),                                     -- Omega-3（抗炎/护脑）
    caffeine_mg         NUMERIC(6,1),                                     -- 咖啡因
    calcium_mg          NUMERIC(7,1),
    iron_mg             NUMERIC(6,1),
    zinc_mg             NUMERIC(6,1),
    magnesium_mg        NUMERIC(7,1),

    -- 额外属性
    glycemic_index      SMALLINT     CHECK (glycemic_index BETWEEN 0 AND 150), -- 升糖指数
    edible_portion_pct  NUMERIC(4,1) DEFAULT 100,                        -- 可食部比例
    is_common           BOOLEAN      DEFAULT FALSE,                       -- 是否常见食物（优先展示）
    is_processed        BOOLEAN      DEFAULT FALSE,                       -- 是否加工食品
    data_source         VARCHAR(128) DEFAULT '中国食物成分表',            -- 数据来源

    -- 向量（pgvector, 1536d 对应 text-embedding-3-small / Claude embedding）
    -- 设计原因：用于语义搜索 "护眼食物" "高蛋白低脂" 等自然语言查询
    embedding           VECTOR(1536),

    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 3.3 食物与适用健康目标关联
CREATE TABLE food_goal_tags (
    food_id             UUID         NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
    goal_type           goal_type_enum NOT NULL,
    relevance           NUMERIC(3,2) DEFAULT 1.0 CHECK (relevance BETWEEN 0 AND 1),
    PRIMARY KEY (food_id, goal_type)
);

-- 3.4 外卖菜品表（对接外卖平台数据）
CREATE TABLE delivery_dishes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform            VARCHAR(32)  NOT NULL,                             -- meituan / eleme
    platform_dish_id    VARCHAR(128) NOT NULL,
    merchant_name       VARCHAR(256) NOT NULL,
    dish_name           VARCHAR(256) NOT NULL,
    price_cent          INTEGER      NOT NULL,                            -- 价格（分）
    image_url           VARCHAR(512),
    merchant_address    VARCHAR(512),
    merchant_lat        NUMERIC(10,7),
    merchant_lng        NUMERIC(10,7),

    -- 估算营养（外卖通常无精确营养数据，AI 估算）
    estimated_kcal      INTEGER,
    estimated_protein_g NUMERIC(5,1),
    estimated_fat_g     NUMERIC(5,1),
    estimated_carbs_g   NUMERIC(5,1),
    health_score        SMALLINT     CHECK (health_score BETWEEN 0 AND 100), -- AI 健康评分 0-100

    raw_data            JSONB,                                            -- 原始平台数据
    synced_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),

    UNIQUE (platform, platform_dish_id)
);

-- ============================================================================
-- 4. 饮食记录域
-- ============================================================================

-- 4.1 饮食记录主表（每餐一条记录）
CREATE TABLE food_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    meal_type           meal_type_enum NOT NULL,
    meal_date           DATE         NOT NULL DEFAULT CURRENT_DATE,
    meal_time           TIME         NOT NULL DEFAULT CURRENT_TIME,
    source              source_type_enum DEFAULT 'manual',               -- 记录来源

    -- 营养汇总（由 food_log_items 汇总计算 + 触发器维护）
    total_kcal          NUMERIC(7,1) DEFAULT 0,
    total_protein_g     NUMERIC(6,1) DEFAULT 0,
    total_fat_g         NUMERIC(6,1) DEFAULT 0,
    total_carbs_g       NUMERIC(6,1) DEFAULT 0,
    total_fiber_g       NUMERIC(6,1) DEFAULT 0,
    total_sodium_mg     NUMERIC(7,1) DEFAULT 0,
    total_caffeine_mg   NUMERIC(6,1) DEFAULT 0,

    -- 用户备注
    mood_before         SMALLINT     CHECK (mood_before BETWEEN 1 AND 5), -- 餐前心情 1-5
    mood_after          SMALLINT     CHECK (mood_after BETWEEN 1 AND 5),
    satiety_level       SMALLINT     CHECK (satiety_level BETWEEN 1 AND 5), -- 饱腹感 1-5
    notes               TEXT,
    photo_url           VARCHAR(512),                                     -- 拍照识别的照片

    -- 上下文
    location            VARCHAR(256),                                     -- 用餐地点
    eaten_with          VARCHAR(256),                                     -- 和谁一起吃
    cost_cent           INTEGER,

    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 4.2 饮食记录明细（一餐中的单种食物）
CREATE TABLE food_log_items (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    food_log_id         UUID         NOT NULL REFERENCES food_logs(id) ON DELETE CASCADE,
    food_id             UUID         REFERENCES foods(id),                -- 关联标准食物库（可空，用户自定义食物时为空）

    -- 食物快照（记录时的食物信息，即使标准库变更也不影响历史记录）
    food_name           VARCHAR(256) NOT NULL,                            -- 食物名称（快照）
    serving_size_g      NUMERIC(7,1) NOT NULL CHECK (serving_size_g > 0), -- 食用份量(g)
    serving_unit        VARCHAR(32)  DEFAULT 'g',                         -- 份量单位

    -- 实际摄入营养（根据份量换算）
    energy_kcal         NUMERIC(7,1) NOT NULL,
    protein_g           NUMERIC(6,1) DEFAULT 0,
    fat_g               NUMERIC(6,1) DEFAULT 0,
    carbs_g             NUMERIC(6,1) DEFAULT 0,
    fiber_g             NUMERIC(6,1) DEFAULT 0,
    sodium_mg           NUMERIC(7,1) DEFAULT 0,
    caffeine_mg         NUMERIC(6,1) DEFAULT 0,

    sort_order          SMALLINT     DEFAULT 0,                           -- 在一餐中的顺序
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 4.3 营养日记每日汇总（物化视图源表，由定时任务 + 触发器维护）
CREATE TABLE daily_nutrition_summary (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    summary_date        DATE         NOT NULL,

    -- 摄入汇总
    total_kcal          NUMERIC(7,1) DEFAULT 0,
    total_protein_g     NUMERIC(6,1) DEFAULT 0,
    total_fat_g         NUMERIC(6,1) DEFAULT 0,
    total_carbs_g       NUMERIC(6,1) DEFAULT 0,
    total_fiber_g       NUMERIC(6,1) DEFAULT 0,
    total_sodium_mg     NUMERIC(7,1) DEFAULT 0,
    total_caffeine_mg   NUMERIC(6,1) DEFAULT 0,

    -- 与目标对比
    kcal_target         INTEGER,
    kcal_achievement_pct NUMERIC(5,1),                                   -- 达成率 %
    meal_count          SMALLINT     DEFAULT 0,                          -- 当日记录餐数

    -- 评分
    nutrition_score     SMALLINT     CHECK (nutrition_score BETWEEN 0 AND 100), -- AI 综合评分
    score_feedback      TEXT,                                             -- AI 评语

    generated_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    UNIQUE (user_id, summary_date)
);

-- ============================================================================
-- 5. Agent 记忆域（AI 核心）
-- ============================================================================

-- 5.1 Agent 记忆主表
-- 设计原因：实现 AI 长期记忆，混合了事实记忆和语义记忆两种范式
-- - memory_type='fact'/'preference' → 结构化知识（类似知识图谱）
-- - memory_type='episode'/'summary' → 对话摘要（带时间衰减权重）
-- - embedding 字段支持 RAG 检索最相关记忆
CREATE TABLE agent_memories (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    memory_type         memory_type_enum NOT NULL,

    -- 记忆内容
    title               VARCHAR(256) NOT NULL,                            -- 记忆概要
    content             TEXT         NOT NULL,                            -- 记忆详情
    key_facts           JSONB        DEFAULT '[]',                        -- 结构化提取的关键事实

    -- 关联与权重
    importance          NUMERIC(3,2) NOT NULL DEFAULT 0.5 CHECK (importance BETWEEN 0 AND 1),
    access_count        INTEGER      NOT NULL DEFAULT 0,                  -- 被检索次数
    last_accessed_at    TIMESTAMPTZ,
    decay_factor        NUMERIC(4,3) DEFAULT 1.0,                        -- Ebbinghaus 遗忘曲线衰减因子

    -- 来源追溯
    source              VARCHAR(64)  DEFAULT 'conversation',              -- conversation / recommendation / food_log / manual
    source_id           UUID,                                              -- 关联源记录 ID（如推荐 ID）
    confidence          NUMERIC(3,2) DEFAULT 1.0 CHECK (confidence BETWEEN 0 AND 1), -- 记忆置信度

    -- 向量（语义搜索）
    embedding           VECTOR(1536),

    -- 时间戳
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expires_at          TIMESTAMPTZ,                                      -- 可选过期时间

    -- 复合索引：按用户 + 重要性 + 时间排序
    CONSTRAINT chk_valid_decay CHECK (decay_factor BETWEEN 0 AND 1)
);

-- 5.2 Agent 记忆关系（连接关联记忆，形成记忆网络）
CREATE TABLE agent_memory_links (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_memory_id    UUID         NOT NULL REFERENCES agent_memories(id) ON DELETE CASCADE,
    target_memory_id    UUID         NOT NULL REFERENCES agent_memories(id) ON DELETE CASCADE,
    relation            VARCHAR(128) NOT NULL,                            -- 关系类型：supports / contradicts / follows / related_to
    weight              NUMERIC(3,2) DEFAULT 1.0,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (source_memory_id, target_memory_id, relation),
    CHECK (source_memory_id <> target_memory_id)
);

-- 5.3 用户饮食偏好学习历史（Agent 从反馈中学习的记录）
CREATE TABLE agent_preference_signals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    food_id             UUID         REFERENCES foods(id),
    food_name           VARCHAR(256),                                     -- 食物名（food_id 为空时的文本描述）

    -- 信号
    signal_type         VARCHAR(32)  NOT NULL,                            -- like / dislike / avoid / crave / tired_of
    signal_strength     NUMERIC(3,2) DEFAULT 0.7 CHECK (signal_strength BETWEEN 0 AND 1),
    signal_source       VARCHAR(64),                                      -- 来源：explicit_feedback / implicit_behavior / ai_inferred
    context             JSONB,                                            -- 触发上下文（时间、地点、场景等）
    occurrence_count    INTEGER      DEFAULT 1,                           -- 信号出现次数

    -- 时间衰减
    last_signal_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ============================================================================
-- 6. 推荐引擎域
-- ============================================================================

-- 6.1 推荐记录主表
CREATE TABLE recommendation_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- 推荐元数据
    recommend_type      VARCHAR(32)  NOT NULL,                            -- meal / daily / weekly / scenario / snack
    scenario            VARCHAR(64),                                      -- 场景标签：overtime / eye_care / hair_care / caffeine_cut 等
    meal_type           meal_type_enum,                                   -- 推荐的目标餐次
    target_date         DATE,

    -- AI 生成过程
    model_name          VARCHAR(64)  NOT NULL,                            -- 使用的 LLM 模型
    model_version       VARCHAR(32),
    prompt_template_id  VARCHAR(64),                                      -- 使用的 Prompt 模板 ID
    retrieval_sources   JSONB,                                            -- RAG 检索到的知识片段 ID 列表

    -- 生成内容
    recommendation_json JSONB        NOT NULL,                            -- 完整推荐结果（结构化 JSON）
    summary_text        TEXT         NOT NULL,                            -- 推荐摘要（给用户看的文本）

    -- Token 消耗（成本追踪）
    prompt_tokens       INTEGER,
    completion_tokens   INTEGER,
    total_tokens        INTEGER,
    latency_ms          INTEGER,                                          -- 推理耗时

    -- 推荐状态
    status              recommend_status_enum DEFAULT 'generated',
    presented_at        TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ,

    -- 用户反馈
    feedback            feedback_enum,                                    -- 用户反馈
    feedback_detail     TEXT,                                             -- 反馈文字（如 "太油了"）
    feedback_at         TIMESTAMPTZ,

    -- 时间戳
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 6.2 推荐结果中的具体餐食/食物
CREATE TABLE recommendation_items (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id   UUID         NOT NULL REFERENCES recommendation_logs(id) ON DELETE CASCADE,

    -- 推荐内容
    item_type           VARCHAR(32)  NOT NULL DEFAULT 'food',             -- food / dish / meal_set / tip
    food_name           VARCHAR(256) NOT NULL,
    food_id             UUID         REFERENCES foods(id),                -- 关联标准食物库
    delivery_dish_id    UUID         REFERENCES delivery_dishes(id),      -- 关联外卖菜品

    serving_size_g      NUMERIC(7,1),
    estimated_kcal      NUMERIC(7,1),
    estimated_protein_g NUMERIC(6,1),
    estimated_fat_g     NUMERIC(6,1),
    estimated_carbs_g   NUMERIC(6,1),

    -- AI 推荐理由
    reason_text         TEXT,                                             -- 为什么推荐这个（可解释性）
    nutrition_tags      TEXT[]       DEFAULT '{}',                        -- 营养亮点标签

    sort_order          SMALLINT     DEFAULT 0,

    -- 用户对此单项的反馈
    item_feedback       feedback_enum,
    was_consumed        BOOLEAN,                                          -- 用户是否实际吃了

    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 6.3 周食谱计划
CREATE TABLE meal_plans (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_week_start     DATE         NOT NULL,                            -- 计划周起始日期（周一）
    plan_name           VARCHAR(256),
    status              VARCHAR(32)  DEFAULT 'active',                    -- active / completed / abandoned

    -- 计划营养目标
    daily_kcal_target   INTEGER,
    daily_protein_g     NUMERIC(6,1),
    daily_fat_g         NUMERIC(6,1),
    daily_carbs_g       NUMERIC(6,1),

    -- 计划生成源
    source_recommendation_id UUID     REFERENCES recommendation_logs(id),

    notes               TEXT,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (user_id, plan_week_start)
);

-- 6.4 周食谱每日明细
CREATE TABLE meal_plan_items (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meal_plan_id        UUID         NOT NULL REFERENCES meal_plans(id) ON DELETE CASCADE,
    plan_date           DATE         NOT NULL,
    meal_type           meal_type_enum NOT NULL,

    food_name           VARCHAR(256) NOT NULL,
    food_id             UUID         REFERENCES foods(id),
    serving_size_g      NUMERIC(7,1),
    estimated_kcal      NUMERIC(7,1),

    is_completed        BOOLEAN      DEFAULT FALSE,                       -- 用户是否按计划执行
    actual_food_log_id  UUID         REFERENCES food_logs(id),            -- 实际记录的饮食

    sort_order          SMALLINT     DEFAULT 0,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ============================================================================
-- 7. 系统辅助表
-- ============================================================================

-- 7.1 Prompt 模板管理
CREATE TABLE prompt_templates (
    id                  VARCHAR(64)  PRIMARY KEY,                         -- 如 "meal_v2" / "daily_v1"
    version             INTEGER      NOT NULL DEFAULT 1,
    name                VARCHAR(128) NOT NULL,
    description         TEXT,
    system_prompt       TEXT         NOT NULL,
    user_prompt_template TEXT        NOT NULL,                            -- 支持 {{variable}} 占位符
    variables           JSONB        DEFAULT '[]',                        -- 变量定义 [{"name":"spice_level","type":"int","required":false}]
    model_preference    VARCHAR(64),                                      -- 推荐模型
    is_active           BOOLEAN      DEFAULT TRUE,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 7.2 通知记录
CREATE TABLE notifications (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel             notification_channel_enum NOT NULL,
    title               VARCHAR(256) NOT NULL,
    body                TEXT         NOT NULL,
    action_url          VARCHAR(512),                                     -- 点击跳转
    is_read             BOOLEAN      DEFAULT FALSE,
    sent_at             TIMESTAMPTZ  NOT NULL DEFAULT now(),
    read_at             TIMESTAMPTZ
);

-- 7.3 用户会话（AI 对话上下文）- 短期记忆
CREATE TABLE chat_sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_type        VARCHAR(32)  DEFAULT 'chat',                      -- chat / onboarding / feedback
    title               VARCHAR(256),
    is_active           BOOLEAN      DEFAULT TRUE,
    context_json        JSONB        DEFAULT '{}',                        -- 会话上下文快照
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE chat_messages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID         NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role                VARCHAR(16)  NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content             TEXT         NOT NULL,
    metadata_json       JSONB        DEFAULT '{}',                        -- token 消耗、模型名等
    embedding           VECTOR(1536),                                     -- 消息向量（用于记忆提取）
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ============================================================================
-- 8. 索引
-- ============================================================================

-- 用户域
CREATE INDEX idx_users_phone               ON users(phone)             WHERE deleted_at IS NULL;
CREATE INDEX idx_users_wechat_union_id     ON users(wechat_union_id)   WHERE deleted_at IS NULL;
CREATE INDEX idx_users_created_at          ON users(created_at);
CREATE INDEX idx_user_health_profiles_user  ON user_health_profiles(user_id);
CREATE INDEX idx_user_allergens_user        ON user_allergens(user_id);
CREATE INDEX idx_user_health_goals_user     ON user_health_goals(user_id) WHERE is_active = TRUE;
CREATE INDEX idx_user_diet_types_user       ON user_diet_types(user_id);

-- 饮食记录域
CREATE INDEX idx_food_logs_user_date       ON food_logs(user_id, meal_date DESC);
CREATE INDEX idx_food_logs_user_meal       ON food_logs(user_id, meal_date, meal_type);
CREATE INDEX idx_food_logs_date            ON food_logs(meal_date);            -- 定时任务按日期汇总
CREATE INDEX idx_food_log_items_log        ON food_log_items(food_log_id);
CREATE INDEX idx_food_log_items_food       ON food_log_items(food_id);
CREATE INDEX idx_daily_summary_user_date   ON daily_nutrition_summary(user_id, summary_date DESC);

-- 食物域
CREATE INDEX idx_foods_category            ON foods(category_id);
CREATE INDEX idx_foods_name_zh             ON foods USING gin(name_zh gin_trgm_ops);  -- 模糊搜索（需要 pg_trgm）
CREATE INDEX idx_foods_embedding           ON foods USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_foods_is_common           ON foods(is_common) WHERE is_common = TRUE;
CREATE INDEX idx_delivery_dishes_platform  ON delivery_dishes(platform, platform_dish_id);
CREATE INDEX idx_delivery_dishes_location  ON delivery_dishes(merchant_lat, merchant_lng);

-- Agent 记忆域
CREATE INDEX idx_agent_memories_user       ON agent_memories(user_id, memory_type);
CREATE INDEX idx_agent_memories_importance ON agent_memories(user_id, importance DESC);
CREATE INDEX idx_agent_memories_embedding  ON agent_memories USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
CREATE INDEX idx_agent_memories_expires    ON agent_memories(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_agent_memory_links_src    ON agent_memory_links(source_memory_id);
CREATE INDEX idx_agent_memory_links_tgt    ON agent_memory_links(target_memory_id);
CREATE INDEX idx_agent_signals_user        ON agent_preference_signals(user_id);
CREATE INDEX idx_agent_signals_food        ON agent_preference_signals(user_id, food_id);

-- 推荐域
CREATE INDEX idx_recommendation_logs_user  ON recommendation_logs(user_id, created_at DESC);
CREATE INDEX idx_recommendation_logs_date  ON recommendation_logs(user_id, target_date);
CREATE INDEX idx_recommendation_logs_fb    ON recommendation_logs(user_id, feedback) WHERE feedback IS NOT NULL;
CREATE INDEX idx_recommendation_items_rec  ON recommendation_items(recommendation_id);
CREATE INDEX idx_meal_plans_user_week      ON meal_plans(user_id, plan_week_start DESC);
CREATE INDEX idx_meal_plan_items_plan      ON meal_plan_items(meal_plan_id, plan_date, meal_type);

-- 系统
CREATE INDEX idx_chat_sessions_user        ON chat_sessions(user_id, updated_at DESC) WHERE is_active = TRUE;
CREATE INDEX idx_chat_messages_session     ON chat_messages(session_id, created_at);
CREATE INDEX idx_notifications_user        ON notifications(user_id, sent_at DESC) WHERE is_read = FALSE;

-- ============================================================================
-- 9. 触发器：自动维护 food_logs 营养汇总
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

CREATE TRIGGER trg_food_log_items_totals
    AFTER INSERT OR UPDATE OR DELETE ON food_log_items
    FOR EACH ROW EXECUTE FUNCTION update_food_log_totals();

-- ============================================================================
-- 10. 触发器：自动计算 BMR + 自动更新 updated_at
-- ============================================================================

-- 10.1 自动计算 BMR（Mifflin-St Jeor 公式）
-- 设计原因：age() 是 STABLE 函数，不能用于 GENERATED ALWAYS，改用触发器计算
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
            NEW.bmr_kcal := ROUND(10 * NEW.weight_kg + 6.25 * NEW.height_cm - 5 * age_years);  -- 中性估算
        END IF;
    ELSE
        NEW.bmr_kcal := NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_bmr_calc
    BEFORE INSERT OR UPDATE OF gender, weight_kg, height_cm, birth_date ON user_health_profiles
    FOR EACH ROW EXECUTE FUNCTION calc_bmr();

-- 10.2 自动更新 updated_at 时间戳
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trg_food_logs_updated_at
    BEFORE UPDATE ON food_logs
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trg_foods_updated_at
    BEFORE UPDATE ON foods
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trg_agent_memories_updated_at
    BEFORE UPDATE ON agent_memories
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trg_recommendation_updated_at
    BEFORE UPDATE ON recommendation_logs
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- ============================================================================
-- 11. 分区表：chat_messages 按会话创建月份分区
-- 设计原因：对话消息量大且随时间线性增长，分区提升查询效率
-- ============================================================================

-- 注意：分区需要在实际创建表时处理，此处仅提供注释方案
-- ALTER TABLE chat_messages
--     PARTITION BY RANGE (created_at);
-- 后续按月创建分区：
-- CREATE TABLE chat_messages_2026_08 PARTITION OF chat_messages
--     FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
-- 建议用 pg_partman 自动管理分区

-- ============================================================================
-- 12. 初始数据：食物分类
-- ============================================================================

INSERT INTO food_categories (category, name_zh, icon_emoji, sort_order) VALUES
    ('staple',     '主食',     '🍚', 1),
    ('meat',       '畜肉',     '🥩', 2),
    ('poultry',    '禽肉',     '🍗', 3),
    ('seafood',    '水产',     '🐟', 4),
    ('egg',        '蛋类',     '🥚', 5),
    ('dairy',      '奶制品',   '🥛', 6),
    ('legume',     '豆类',     '🫘', 7),
    ('vegetable',  '蔬菜',     '🥬', 8),
    ('fruit',      '水果',     '🍎', 9),
    ('nut',        '坚果种子', '🥜', 10),
    ('oil',        '油脂',     '🫒', 11),
    ('beverage',   '饮料',     '🥤', 12),
    ('snack',      '零食',     '🍪', 13),
    ('condiment',  '调味品',   '🧂', 14),
    ('supplement', '补剂',     '💊', 15),
    ('mixed_dish', '混合菜肴', '🍲', 16),
    ('fast_food',  '快餐',     '🍔', 17),
    ('other',      '其他',     '📦', 99);
