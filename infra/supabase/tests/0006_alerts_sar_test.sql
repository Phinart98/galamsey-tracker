-- 0006_alerts_sar_test.sql
-- pgTAP smoke test for migration 0006 + 0007:
--   SAR alerts schema + helpers + Martin MVT fn + RLS + admin-fn lockdown.
-- Run with: pg_prove -d galamsey_test infra/supabase/tests/0006_alerts_sar_test.sql
--
-- WHY 2-arg has_index: see 0003_alerts_gfw_test.sql header comment.

BEGIN;

SELECT plan(26);

-- Table existence
SELECT has_table('alerts_sar', 'alerts_sar table should exist');

-- Indexes (existence only; column lists are documented in 0006)
SELECT has_index('alerts_sar', 'idx_alerts_sar_geom');
SELECT has_index('alerts_sar', 'idx_alerts_sar_period_conf');
SELECT has_index('alerts_sar', 'idx_alerts_sar_region');
SELECT has_index('alerts_sar', 'idx_alerts_sar_reserve');
SELECT has_index('alerts_sar', 'idx_alerts_sar_medium_high');

-- Not-null constraints
SELECT col_not_null('alerts_sar', 'alert_uid');
SELECT col_not_null('alerts_sar', 'detection_period_start');
SELECT col_not_null('alerts_sar', 'detection_period_end');
SELECT col_not_null('alerts_sar', 'area_ha');
SELECT col_not_null('alerts_sar', 'confidence');
SELECT col_not_null('alerts_sar', 'geom');

-- Functions exist
SELECT has_function('public', 'sar_alerts_join_admin', ARRAY['bigint']);
SELECT has_function('public', 'sar_alerts_mvt',        ARRAY['integer','integer','integer','json']);

-- Round-trip insert
INSERT INTO alerts_sar (
  alert_uid, detection_period_start, detection_period_end,
  area_ha, delta_db_mean, delta_db_max, confidence, geom
) VALUES (
  'test_sar_001', '2026-04-01', '2026-04-30',
  1.234, 2.50, 4.20, 'medium',
  ST_Multi(ST_SetSRID(ST_GeomFromText(
    'POLYGON((-1.55 6.45, -1.50 6.45, -1.50 6.50, -1.55 6.50, -1.55 6.45))'
  ), 4326))
);
SELECT ok(
  (SELECT count(*) = 1 FROM alerts_sar WHERE alert_uid = 'test_sar_001'),
  'inserted SAR alert is readable in same transaction'
);

-- CHECK constraints reject bad values
SELECT throws_ok(
  $$ INSERT INTO alerts_sar (
       alert_uid, detection_period_start, detection_period_end,
       area_ha, confidence, geom
     ) VALUES (
       'bad_conf', '2026-04-01', '2026-04-30',
       1.0, 'extreme',
       ST_Multi(ST_SetSRID(ST_GeomFromText(
         'POLYGON((-1.5 6.4, -1.4 6.4, -1.4 6.5, -1.5 6.5, -1.5 6.4))'
       ), 4326))
     ) $$,
  '23514', NULL, 'confidence CHECK rejects values outside the enum'
);

SELECT throws_ok(
  $$ INSERT INTO alerts_sar (
       alert_uid, detection_period_start, detection_period_end,
       area_ha, confidence, geom
     ) VALUES (
       'bad_period', '2026-05-01', '2026-04-01',
       1.0, 'medium',
       ST_Multi(ST_SetSRID(ST_GeomFromText(
         'POLYGON((-1.5 6.4, -1.4 6.4, -1.4 6.5, -1.5 6.5, -1.5 6.4))'
       ), 4326))
     ) $$,
  '23514', NULL, 'period_chk rejects end < start'
);

-- Martin MVT function returns bytea for a Ghana-area tile
SELECT ok(
  (SELECT sar_alerts_mvt(4, 7, 7, json_build_object(
     'from', '2026-04-01',
     'to',   '2026-04-30',
     'min_confidence', 'low')) IS NOT NULL),
  'sar_alerts_mvt returns non-null bytea for Ghana z=4 tile (7,7)'
);

-- Defensive parsing: malformed inputs must NOT raise; they must fall back
-- to safe defaults so a single bad request can't 500 the public SAR layer.
SELECT ok(
  (SELECT sar_alerts_mvt(4, 7, 7, json_build_object('from','not-a-date','to','2026-04-30')) IS NOT NULL),
  'sar_alerts_mvt swallows invalid from-date and falls back to default'
);
SELECT ok(
  (SELECT sar_alerts_mvt(4, 7, 7, json_build_object('from','2026-04-01','to','garbage')) IS NOT NULL),
  'sar_alerts_mvt swallows invalid to-date and falls back to default'
);
SELECT ok(
  (SELECT sar_alerts_mvt(4, 7, 7, json_build_object('min_confidence','lowwww')) IS NOT NULL),
  'sar_alerts_mvt normalises unknown min_confidence to medium'
);

-- Functional test for sar_alerts_join_admin: insert a polygon inside a
-- known fixture region, run the function, assert region_id gets populated.
-- Without this, a misconfigured ST_Contains predicate (wrong arg order,
-- wrong fn) would silently produce NULL FKs and zero pgTAP failures.
--
-- Coords are east of Ghana's bbox (which ends ~1.2 E) so the fixture region
-- is the ONLY region containing the test polygon -- otherwise the seeded
-- Ghana admin layer would match first.
INSERT INTO regions (gid_1, name, geom, as_of, source_url)
VALUES ('TEST-PGTAP-RGN', 'pgtap Region',
        ST_Multi(ST_SetSRID(ST_GeomFromText(
          'POLYGON((4.0 0.0, 6.0 0.0, 6.0 2.0, 4.0 2.0, 4.0 0.0))'
        ), 4326)),
        CURRENT_DATE, 'pgtap-fixture');

INSERT INTO pipeline_runs (pipeline_name, started_at, status)
VALUES ('pgtap_join_admin', now(), 'running');

INSERT INTO alerts_sar (
  alert_uid, detection_period_start, detection_period_end,
  area_ha, delta_db_mean, delta_db_max, confidence, geom, pipeline_run_id
)
SELECT
  'test_join_admin_001', '2026-04-01', '2026-04-30',
  1.0, 2.5, 4.0, 'medium',
  ST_Multi(ST_SetSRID(ST_GeomFromText(
    'POLYGON((4.5 0.5, 5.5 0.5, 5.5 1.5, 4.5 1.5, 4.5 0.5))'
  ), 4326)),
  pr.id
FROM pipeline_runs pr WHERE pr.pipeline_name='pgtap_join_admin';

SELECT sar_alerts_join_admin(pr.id)
FROM pipeline_runs pr
WHERE pr.pipeline_name='pgtap_join_admin';

SELECT is(
  (SELECT region_id FROM alerts_sar WHERE alert_uid = 'test_join_admin_001'),
  (SELECT id FROM regions WHERE gid_1 = 'TEST-PGTAP-RGN'),
  'sar_alerts_join_admin populates region_id with the matching region'
);

-- RLS: anon can SELECT, cannot INSERT
SET LOCAL ROLE anon;

SELECT lives_ok(
  $$ SELECT count(*) FROM alerts_sar $$,
  'anon can SELECT from alerts_sar'
);

SELECT throws_ok(
  $$ INSERT INTO alerts_sar (
       alert_uid, detection_period_start, detection_period_end,
       area_ha, confidence, geom
     ) VALUES (
       'anon_insert', '2026-04-01', '2026-04-30',
       1.0, 'medium',
       ST_Multi(ST_SetSRID(ST_GeomFromText(
         'POLYGON((-1.5 6.4, -1.4 6.4, -1.4 6.5, -1.5 6.5, -1.5 6.4))'
       ), 4326))
     ) $$,
  '42501', NULL, 'anon cannot INSERT into alerts_sar'
);

-- anon can EXECUTE sar_alerts_mvt (granted in 0006)
SELECT lives_ok(
  $$ SELECT sar_alerts_mvt(4, 7, 7, json_build_object('from','2026-04-01','to','2026-04-30')) $$,
  'anon can EXECUTE sar_alerts_mvt'
);

-- 0007: anon CANNOT EXECUTE the maintenance function
SELECT throws_ok(
  $$ SELECT sar_alerts_join_admin(1) $$,
  '42501', NULL, 'anon cannot EXECUTE sar_alerts_join_admin (locked in 0007)'
);

RESET ROLE;

SELECT * FROM finish();

ROLLBACK;
