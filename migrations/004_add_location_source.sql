-- Migration 004: user_health_profiles — add location_source
DO $$ BEGIN
  ALTER TABLE user_health_profiles ADD COLUMN location_source VARCHAR(32) DEFAULT 'gps';
EXCEPTION WHEN duplicate_column THEN null;
END $$;
