-- ============================================================================
-- NutriAgent — All Pending Migrations (safe to re-run)
-- Paste into Supabase SQL Editor: https://adlnnplssonkioyojrhq.supabase.co
-- ============================================================================

-- 001: food_log_items columns
ALTER TABLE food_log_items ADD COLUMN IF NOT EXISTS quantity NUMERIC(5,1);
ALTER TABLE food_log_items ADD COLUMN IF NOT EXISTS confidence NUMERIC(3,2);

-- 002: foods unique constraint
DO $$ BEGIN ALTER TABLE foods ADD CONSTRAINT foods_name_zh_key UNIQUE (name_zh); EXCEPTION WHEN duplicate_table THEN null; END $$;

-- 003: user_health_profiles location
ALTER TABLE user_health_profiles ADD COLUMN IF NOT EXISTS city VARCHAR(64);
ALTER TABLE user_health_profiles ADD COLUMN IF NOT EXISTS district VARCHAR(64);
ALTER TABLE user_health_profiles ADD COLUMN IF NOT EXISTS province VARCHAR(64);
ALTER TABLE user_health_profiles ADD COLUMN IF NOT EXISTS latitude NUMERIC(10,7);
ALTER TABLE user_health_profiles ADD COLUMN IF NOT EXISTS longitude NUMERIC(10,7);
ALTER TABLE user_health_profiles ADD COLUMN IF NOT EXISTS location_updated_at TIMESTAMPTZ;

-- 004: location_source
ALTER TABLE user_health_profiles ADD COLUMN IF NOT EXISTS location_source VARCHAR(32) DEFAULT 'gps';

-- 005: user_nutrition_preferences
CREATE TABLE IF NOT EXISTS user_nutrition_preferences (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    preference_type VARCHAR(32) NOT NULL,
    preference_key  VARCHAR(128) NOT NULL,
    preference_value VARCHAR(256),
    confidence      NUMERIC(3,2) DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
    source          VARCHAR(64) DEFAULT 'manual',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, preference_type, preference_key)
);
CREATE INDEX IF NOT EXISTS idx_user_nutr_prefs_user ON user_nutrition_preferences(user_id, preference_type);

-- 006: last_confirmed_at
ALTER TABLE user_nutrition_preferences ADD COLUMN IF NOT EXISTS last_confirmed_at TIMESTAMPTZ;

-- 007: agent observability
CREATE TABLE IF NOT EXISTS agent_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_name      VARCHAR(64) NOT NULL,
    request_id      VARCHAR(64),
    input_summary   TEXT,
    output_summary  TEXT,
    status          VARCHAR(16) DEFAULT 'running',
    latency_ms      INTEGER,
    token_usage     INTEGER,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS recommendation_feedback (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recommendation_id UUID,
    rating            SMALLINT CHECK (rating >= 1 AND rating <= 5),
    accepted          BOOLEAN,
    comment           TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 008: indexes
CREATE INDEX IF NOT EXISTS idx_agent_runs_user ON agent_runs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_agent ON agent_runs(agent_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rec_feedback_user ON recommendation_feedback(user_id, created_at DESC);

-- Verify
SELECT 'OK' AS status, count(*) AS tables FROM information_schema.tables WHERE table_schema='public';
