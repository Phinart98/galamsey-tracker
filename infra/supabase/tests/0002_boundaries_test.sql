-- 0002_boundaries_test.sql
-- pgTAP smoke test for migration 0002: boundaries schema.
-- Run with: pg_prove -d galamsey_test infra/supabase/tests/0002_boundaries_test.sql

BEGIN;

SELECT plan(25);

-- ── Table existence ──────────────────────────────────────────────────────────
SELECT has_table('pipeline_runs',   'pipeline_runs table should exist');
SELECT has_table('regions',         'regions table should exist');
SELECT has_table('districts',       'districts table should exist');
SELECT has_table('forest_reserves', 'forest_reserves table should exist');
SELECT has_table('water_bodies',    'water_bodies table should exist');
SELECT has_table('concessions',     'concessions table should exist');

-- ── GIST spatial indexes ─────────────────────────────────────────────────────
SELECT has_index('regions',         'idx_regions_geom',           'regions should have GIST index on geom');
SELECT has_index('districts',       'idx_districts_geom',         'districts should have GIST index on geom');
SELECT has_index('forest_reserves', 'idx_forest_reserves_geom',   'forest_reserves should have GIST index on geom');
SELECT has_index('water_bodies',    'idx_water_bodies_geom',      'water_bodies should have GIST index on geom');
SELECT has_index('concessions',     'idx_concessions_geom',       'concessions should have GIST index on geom');

-- ── Other key indexes ────────────────────────────────────────────────────────
SELECT has_index('concessions', 'idx_concessions_holder_normalised', 'concessions should index holder_name_normalised');
SELECT has_index('concessions', 'idx_concessions_last_seen_at',      'concessions should index last_seen_at');
SELECT has_index('districts',   'idx_districts_region_id',           'districts should index region_id FK');

-- ── Not-null constraints ─────────────────────────────────────────────────────
SELECT col_not_null('pipeline_runs', 'pipeline_name', 'pipeline_runs.pipeline_name must not be null');
SELECT col_not_null('pipeline_runs', 'status',        'pipeline_runs.status must not be null');
SELECT col_not_null('regions',       'gid_1',         'regions.gid_1 must not be null');
SELECT col_not_null('concessions',   'cadastre_uid',  'concessions.cadastre_uid must not be null');
SELECT col_not_null('concessions',   'holder_name',   'concessions.holder_name must not be null');

-- ── Round-trip: insert a region, verify it's readable within the transaction ──
INSERT INTO regions (gid_1, name, geom, as_of, source_url) VALUES (
  'GHA.TEST_1',
  'Test Region',
  ST_Multi(ST_GeomFromText('POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))', 4326)),
  '2024-01-01',
  'https://example.com/test'
);

SELECT ok(
  (SELECT count(*) = 1 FROM regions WHERE gid_1 = 'GHA.TEST_1'),
  'inserted region should be readable in same transaction'
);

-- ── Seed a pipeline_runs row so the RLS visibility test below is meaningful ──
INSERT INTO pipeline_runs (pipeline_name, status) VALUES ('test-pipeline', 'running');

-- ── RLS: anon can SELECT from public reference tables ───────────────────────
SET LOCAL ROLE anon;

SELECT lives_ok(
  $$ SELECT count(*) FROM regions $$,
  'anon can SELECT from regions'
);

SELECT lives_ok(
  $$ SELECT count(*) FROM districts $$,
  'anon can SELECT from districts'
);

SELECT lives_ok(
  $$ SELECT count(*) FROM concessions $$,
  'anon can SELECT from concessions'
);

-- ── RLS: anon cannot INSERT into public reference tables ─────────────────────
SELECT throws_ok(
  $$ INSERT INTO regions (gid_1, name, geom, as_of, source_url)
     VALUES ('GHA.ANON_1', 'Anon Region',
       ST_Multi(ST_GeomFromText('POLYGON((2 2, 3 2, 3 3, 2 3, 2 2))', 4326)),
       '2024-01-01', 'https://example.com/anon') $$,
  '42501',
  NULL,
  'anon cannot INSERT into regions'
);

-- ── RLS: anon cannot read pipeline_runs (no anon SELECT policy = deny all) ──
SELECT ok(
  (SELECT count(*) = 0 FROM pipeline_runs),
  'anon sees zero rows from pipeline_runs (RLS: no SELECT policy)'
);

RESET ROLE;

SELECT * FROM finish();

ROLLBACK;
