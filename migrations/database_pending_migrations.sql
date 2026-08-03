-- ============================================================================
-- NutriAgent — Pending Migrations
-- Run in Supabase SQL Editor (safe to re-run)
-- Generated: 2026-08-03
-- ============================================================================

-- ── 1. food_log_items: add quantity + confidence ──────────
-- Risk: 🟢 Low — new columns, no data migration needed
-- Run: ONCE
DO $$ BEGIN
    ALTER TABLE food_log_items ADD COLUMN quantity NUMERIC(5,1);
EXCEPTION WHEN duplicate_column THEN null;
END $$;

DO $$ BEGIN
    ALTER TABLE food_log_items ADD COLUMN confidence NUMERIC(3,2);
EXCEPTION WHEN duplicate_column THEN null;
END $$;

-- ── 2. foods: unique constraint on name_zh ───────────────
-- Risk: 🟡 Medium — fails if duplicate names exist (check first)
-- Run: ONCE
SELECT name_zh, count(*) FROM foods GROUP BY name_zh HAVING count(*) > 1;
-- If no rows: safe to run. If duplicates: deduplicate first.
DO $$ BEGIN
    ALTER TABLE foods ADD CONSTRAINT foods_name_zh_key UNIQUE (name_zh);
EXCEPTION WHEN duplicate_table THEN null;
END $$;

-- ── 3. Verify ─────────────────────────────────────────────
-- Run: anytime
SELECT 'quantity' AS col, count(*) AS exists FROM information_schema.columns WHERE table_name='food_log_items' AND column_name='quantity'
UNION ALL
SELECT 'confidence', count(*) FROM information_schema.columns WHERE table_name='food_log_items' AND column_name='confidence'
UNION ALL
SELECT 'foods UNIQUE', count(*) FROM pg_constraint WHERE conname='foods_name_zh_key'
UNION ALL
SELECT 'foods with embedding', count(*) FROM foods WHERE embedding IS NOT NULL;
