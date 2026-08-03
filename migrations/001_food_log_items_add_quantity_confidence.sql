-- ============================================================================
-- Migration 001: food_log_items — add quantity + confidence columns
-- Run: psql <DATABASE_URL> -f migrations/001_food_log_items_add_quantity_confidence.sql
-- Safe to re-run: uses IF NOT EXISTS / IF EXISTS patterns
-- ============================================================================

-- 1. Add quantity column (user-facing quantity, e.g., "2 eggs")
DO $$ BEGIN
    ALTER TABLE food_log_items ADD COLUMN quantity NUMERIC(5,1);
EXCEPTION WHEN duplicate_column THEN null;
END $$;

-- 2. Add confidence column (AI recognition confidence 0-1)
DO $$ BEGIN
    ALTER TABLE food_log_items ADD COLUMN confidence NUMERIC(3,2);
EXCEPTION WHEN duplicate_column THEN null;
END $$;

-- 3. Add check constraints (only if columns were just created)
DO $$ BEGIN
    ALTER TABLE food_log_items ADD CONSTRAINT chk_quantity_positive CHECK (quantity > 0);
EXCEPTION WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    ALTER TABLE food_log_items ADD CONSTRAINT chk_confidence_range CHECK (confidence >= 0 AND confidence <= 1);
EXCEPTION WHEN duplicate_object THEN null;
END $$;

-- 4. Verify
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'food_log_items'
  AND column_name IN ('quantity', 'confidence')
ORDER BY column_name;
