-- 0001_init_postgis.sql
-- Foundation: extensions + performance monitoring + testing infrastructure.
-- See infra/supabase/migrations/README.md for schema conventions.

-- ── Geospatial ───────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;

-- ── Scheduling ───────────────────────────────────────────────────────────────
-- pg_cron drives: alert partition creation (1st of month), materialized view
-- refreshes (hourly / daily), and report auto-expiry (daily).
-- On Supabase Cloud, pg_cron is a trusted extension — no superuser required.
-- Jobs are always created in subsequent migrations, never here.
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- ── Performance monitoring ────────────────────────────────────────────────────
-- pg_stat_statements is already active on Supabase Pro (track = 'all').
-- The CREATE below is a no-op there; it installs the extension in local/CI
-- Postgres containers where it isn't pre-loaded.
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- ── Crypto / UUIDs ───────────────────────────────────────────────────────────
-- gen_random_uuid() is built-in on PG13+; pgcrypto adds encode/decode and
-- digest() which we use for alert_uid deduplication hashes.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── Testing (pgTAP) ──────────────────────────────────────────────────────────
-- pgTAP runs in the ephemeral CI Postgres container only.
-- On Supabase Cloud it is not available — the IF NOT EXISTS keeps this safe.
-- Test files live in infra/supabase/tests/ and run via pg_prove in CI.
CREATE EXTENSION IF NOT EXISTS pgtap;

-- ── Row-Level Security — global default ──────────────────────────────────────
-- CONVENTION: every table created in this project MUST immediately follow
-- its CREATE TABLE with:
--   ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
-- The default is DENY ALL. Permissive policies are added per-table in the
-- same migration. See README.md "RLS policy conventions".
--
-- This DO block enforces that the core extensions are present.
-- If any extension failed to install, the migration aborts here in CI.
DO $$
DECLARE
  ext_count INT;
  -- pgtap excluded: it is only available in CI, not on Supabase Cloud production.
  required_exts TEXT[] := ARRAY[
    'postgis', 'fuzzystrmatch', 'pg_cron', 'pg_stat_statements', 'pgcrypto'
  ];
BEGIN
  SELECT COUNT(*) INTO ext_count
  FROM pg_extension
  WHERE extname = ANY(required_exts);

  IF ext_count < array_length(required_exts, 1) THEN
    RAISE EXCEPTION
      'Extension check failed: only % of % required extensions installed. '
      'Ensure pg_cron and pg_stat_statements are in shared_preload_libraries.',
      ext_count, array_length(required_exts, 1);
  END IF;
END;
$$;
