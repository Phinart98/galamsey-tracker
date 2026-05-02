-- 0001_init_postgis_test.sql
-- pgTAP smoke test for migration 0001: extension installation.
-- Run with: pg_prove -d galamsey_test infra/supabase/tests/0001_init_postgis_test.sql

-- NOTE: this test file is CI-only. Run against the ephemeral Postgres
-- container defined in .github/workflows/ci.yml, not against Supabase Cloud
-- (pg_cron and pgtap are not available on Supabase Cloud without the Pro plan
-- configuration; running `supabase test db` here will fail on those two
-- assertions).

BEGIN;

SELECT plan(6);

-- Core geospatial extensions (available everywhere)
SELECT has_extension('postgis',       'postgis extension should be installed');
SELECT has_extension('fuzzystrmatch', 'fuzzystrmatch extension should be installed');
SELECT has_extension('pgcrypto',      'pgcrypto extension should be installed');

-- Extensions that require shared_preload_libraries (configured in CI, and
-- pre-loaded by Supabase Cloud in production)
SELECT has_extension('pg_cron',            'pg_cron extension should be installed');
SELECT has_extension('pg_stat_statements', 'pg_stat_statements should be installed');

-- PostGIS version sanity check: must be >= 3.0
SELECT ok(
  (SELECT split_part(PostGIS_Lib_Version(), '.', 1)::int >= 3),
  'PostGIS version should be >= 3.0'
);

SELECT * FROM finish();

ROLLBACK;
