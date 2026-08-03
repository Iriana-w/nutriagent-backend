-- Migration 006: user_nutrition_preferences — add last_confirmed_at
DO $$ BEGIN
  ALTER TABLE user_nutrition_preferences ADD COLUMN last_confirmed_at TIMESTAMPTZ;
EXCEPTION WHEN duplicate_column THEN null;
END $$;
