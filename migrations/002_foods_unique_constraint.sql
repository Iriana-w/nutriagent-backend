-- Migration 002: Add unique constraint on foods.name_zh
-- PostgreSQL-compatible idempotent pattern

DO $$ BEGIN
    ALTER TABLE foods ADD CONSTRAINT foods_name_zh_key UNIQUE (name_zh);
EXCEPTION WHEN duplicate_table THEN null;
END $$;
