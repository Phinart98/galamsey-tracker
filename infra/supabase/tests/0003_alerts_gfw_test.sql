-- 0003_alerts_gfw_test.sql
-- pgTAP smoke test for migration 0003 + 0004 + 0005:
--   GFW alerts schema + helpers + Martin MVT fn + RLS + admin-fn lockdown.
-- Run with: pg_prove -d galamsey_test infra/supabase/tests/0003_alerts_gfw_test.sql
--
-- WHY 2-arg has_index: pgTAP's 3-arg has_index(table, name, X) interprets X as
-- the expected column list, NOT a description. Multi-word descriptions in the
-- 3rd slot caused 3/21 failures during live verification. The 2-arg form just
-- asserts the index exists, which is what we want here.

BEGIN;

SELECT plan(23);

-- Table existence
SELECT has_table('alerts_gfw', 'alerts_gfw table should exist');

-- Indexes (existence only; column lists are documented in 0003)
SELECT has_index('alerts_gfw', 'idx_alerts_gfw_geom');
SELECT has_index('alerts_gfw', 'idx_alerts_gfw_date_conf');
SELECT has_index('alerts_gfw', 'idx_alerts_gfw_region');
SELECT has_index('alerts_gfw', 'idx_alerts_gfw_source_date');
SELECT has_index('alerts_gfw', 'idx_alerts_gfw_high_conf');

-- Not-null constraints
SELECT col_not_null('alerts_gfw', 'alert_uid');
SELECT col_not_null('alerts_gfw', 'alert_date');
SELECT col_not_null('alerts_gfw', 'source');
SELECT col_not_null('alerts_gfw', 'confidence');
SELECT col_not_null('alerts_gfw', 'geom');

-- Functions exist
SELECT has_function('public', 'ensure_alert_partitions', ARRAY['integer']);
SELECT has_function('public', 'alerts_gfw_join_admin',   ARRAY['bigint']);
SELECT has_function('public', 'gfw_alerts_mvt',          ARRAY['integer','integer','integer','json']);

-- Round-trip insert with the value the Phase 2 pipeline writes ('integrated' from 0004)
INSERT INTO alerts_gfw (alert_uid, alert_date, source, confidence, geom) VALUES (
  'test_uid_001', CURRENT_DATE, 'integrated', 'highest',
  ST_SetSRID(ST_MakePoint(-1.5, 6.5), 4326)
);
SELECT ok(
  (SELECT count(*) = 1 FROM alerts_gfw WHERE alert_uid = 'test_uid_001'),
  'inserted alert is readable in same transaction'
);

-- CHECK constraints reject bad values
SELECT throws_ok(
  $$ INSERT INTO alerts_gfw (alert_uid, alert_date, source, confidence, geom)
     VALUES ('bad_source', CURRENT_DATE, 'unknown_sensor', 'highest',
             ST_SetSRID(ST_MakePoint(-1.5, 6.5), 4326)) $$,
  '23514', NULL, 'source CHECK rejects values outside the enum'
);
SELECT throws_ok(
  $$ INSERT INTO alerts_gfw (alert_uid, alert_date, source, confidence, geom)
     VALUES ('bad_conf', CURRENT_DATE, 'integrated', 'super_sure',
             ST_SetSRID(ST_MakePoint(-1.5, 6.5), 4326)) $$,
  '23514', NULL, 'confidence CHECK rejects values outside the enum'
);

-- Martin MVT function returns bytea for a Ghana-area tile
SELECT ok(
  (SELECT gfw_alerts_mvt(4, 7, 7, json_build_object(
     'from', (CURRENT_DATE - INTERVAL '7 days')::TEXT,
     'to',   CURRENT_DATE::TEXT,
     'min_confidence', 'low')) IS NOT NULL),
  'gfw_alerts_mvt returns non-null bytea for Ghana z=4 tile (7,7)'
);

-- RLS: anon can SELECT, cannot INSERT
SET LOCAL ROLE anon;

SELECT lives_ok(
  $$ SELECT count(*) FROM alerts_gfw $$,
  'anon can SELECT from alerts_gfw'
);

SELECT throws_ok(
  $$ INSERT INTO alerts_gfw (alert_uid, alert_date, source, confidence, geom)
     VALUES ('anon_insert_attempt', CURRENT_DATE, 'integrated', 'high',
             ST_SetSRID(ST_MakePoint(-1.5, 6.5), 4326)) $$,
  '42501', NULL, 'anon cannot INSERT into alerts_gfw'
);

-- anon can EXECUTE gfw_alerts_mvt (granted in 0003)
SELECT lives_ok(
  $$ SELECT gfw_alerts_mvt(4, 7, 7, json_build_object('from','2025-01-01','to','2025-12-31')) $$,
  'anon can EXECUTE gfw_alerts_mvt'
);

-- 0005: anon CANNOT EXECUTE the maintenance functions
SELECT throws_ok(
  $$ SELECT alerts_gfw_join_admin(1) $$,
  '42501', NULL, 'anon cannot EXECUTE alerts_gfw_join_admin (locked in 0005)'
);
SELECT throws_ok(
  $$ SELECT ensure_alert_partitions(3) $$,
  '42501', NULL, 'anon cannot EXECUTE ensure_alert_partitions (locked in 0005)'
);

RESET ROLE;

SELECT * FROM finish();

ROLLBACK;
