-- Migration 003: user_health_profiles — add location fields
-- Safe to re-run (IF NOT EXISTS pattern)

DO $$ BEGIN ALTER TABLE user_health_profiles ADD COLUMN city VARCHAR(64); EXCEPTION WHEN duplicate_column THEN null; END $$;
DO $$ BEGIN ALTER TABLE user_health_profiles ADD COLUMN district VARCHAR(64); EXCEPTION WHEN duplicate_column THEN null; END $$;
DO $$ BEGIN ALTER TABLE user_health_profiles ADD COLUMN province VARCHAR(64); EXCEPTION WHEN duplicate_column THEN null; END $$;
DO $$ BEGIN ALTER TABLE user_health_profiles ADD COLUMN latitude NUMERIC(10,7); EXCEPTION WHEN duplicate_column THEN null; END $$;
DO $$ BEGIN ALTER TABLE user_health_profiles ADD COLUMN longitude NUMERIC(10,7); EXCEPTION WHEN duplicate_column THEN null; END $$;
DO $$ BEGIN ALTER TABLE user_health_profiles ADD COLUMN location_updated_at TIMESTAMPTZ; EXCEPTION WHEN duplicate_column THEN null; END $$;

SELECT column_name FROM information_schema.columns WHERE table_name='user_health_profiles' AND column_name IN ('city','district','province','latitude','longitude','location_updated_at') ORDER BY column_name;
