-- Migration 005: user_nutrition_preferences table
CREATE TABLE IF NOT EXISTS user_nutrition_preferences (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    preference_type VARCHAR(32) NOT NULL,   -- food_like, food_dislike, budget, cuisine, cooking, timing
    preference_key  VARCHAR(128) NOT NULL,  -- e.g., '香菜', '鸡肉', 'budget_level'
    preference_value VARCHAR(256),          -- e.g., 'dislike', 'high_protein', '3000'
    confidence      NUMERIC(3,2) DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
    source          VARCHAR(64) DEFAULT 'manual',  -- manual, chat_extract, food_log_infer, ai_analyze
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, preference_type, preference_key)
);

CREATE INDEX IF NOT EXISTS idx_user_nutr_prefs_user ON user_nutrition_preferences(user_id, preference_type);
