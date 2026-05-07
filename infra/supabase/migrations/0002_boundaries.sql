-- 0002_boundaries.sql
-- Static reference layers + concessions cadastre + pipeline observability.
-- Conventions: see infra/supabase/migrations/README.md and plan section 3a.

-- ── Pipeline observability ───────────────────────────────────────────────────
-- Every ingestion run (concessions, GFW alerts, SAR, NDTI, news) writes one
-- row here so we can trace alerts back to their run and re-do failed runs
-- idempotently. No RLS policy means anon cannot read it; service_role bypasses.
CREATE TABLE pipeline_runs (
  id           BIGSERIAL PRIMARY KEY,
  pipeline_name TEXT NOT NULL,
  started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at  TIMESTAMPTZ,
  rows_inserted INT,
  status       TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')),
  notes        TEXT
);
ALTER TABLE pipeline_runs ENABLE ROW LEVEL SECURITY;

CREATE INDEX idx_pipeline_runs_name_started
  ON pipeline_runs (pipeline_name, started_at DESC);

-- ── Regions (admin level 1) ──────────────────────────────────────────────────
CREATE TABLE regions (
  id         INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  gid_1      TEXT UNIQUE NOT NULL,
  name       TEXT NOT NULL,
  name_alt   TEXT,
  geom       GEOMETRY(MultiPolygon, 4326) NOT NULL,
  as_of      DATE NOT NULL,
  source_url TEXT NOT NULL
);
ALTER TABLE regions ENABLE ROW LEVEL SECURITY;
CREATE POLICY regions_anon_select  ON regions FOR SELECT TO anon          USING (true);
CREATE POLICY regions_auth_select  ON regions FOR SELECT TO authenticated USING (true);
CREATE INDEX idx_regions_geom ON regions USING GIST (geom);

-- ── Districts (admin level 2) ────────────────────────────────────────────────
CREATE TABLE districts (
  id         INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  gid_2      TEXT UNIQUE NOT NULL,
  region_id  INT NOT NULL REFERENCES regions(id) ON DELETE RESTRICT,
  name       TEXT NOT NULL,
  geom       GEOMETRY(MultiPolygon, 4326) NOT NULL,
  as_of      DATE NOT NULL,
  source_url TEXT NOT NULL
);
ALTER TABLE districts ENABLE ROW LEVEL SECURITY;
CREATE POLICY districts_anon_select ON districts FOR SELECT TO anon          USING (true);
CREATE POLICY districts_auth_select ON districts FOR SELECT TO authenticated USING (true);
CREATE INDEX idx_districts_geom      ON districts USING GIST (geom);
CREATE INDEX idx_districts_region_id ON districts (region_id);

-- ── Forest reserves ──────────────────────────────────────────────────────────
-- source = 'forestry_commission' | 'osm' | 'manual_press' (the 44-degraded list).
CREATE TABLE forest_reserves (
  id         INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name       TEXT NOT NULL,
  region_id  INT REFERENCES regions(id) ON DELETE SET NULL,
  area_ha    NUMERIC,
  geom       GEOMETRY(MultiPolygon, 4326) NOT NULL,
  as_of      DATE NOT NULL,
  source     TEXT NOT NULL CHECK (source IN ('forestry_commission', 'osm', 'manual_press')),
  source_url TEXT NOT NULL
);
ALTER TABLE forest_reserves ENABLE ROW LEVEL SECURITY;
CREATE POLICY forest_reserves_anon_select ON forest_reserves FOR SELECT TO anon          USING (true);
CREATE POLICY forest_reserves_auth_select ON forest_reserves FOR SELECT TO authenticated USING (true);
CREATE INDEX idx_forest_reserves_geom      ON forest_reserves USING GIST (geom);
CREATE INDEX idx_forest_reserves_region_id ON forest_reserves (region_id);

-- ── Water bodies ─────────────────────────────────────────────────────────────
CREATE TABLE water_bodies (
  id         INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name       TEXT NOT NULL,
  kind       TEXT NOT NULL CHECK (kind IN ('river', 'lake', 'reservoir')),
  basin      TEXT,
  geom       GEOMETRY(MultiPolygon, 4326) NOT NULL,
  as_of      DATE NOT NULL,
  source_url TEXT NOT NULL
);
ALTER TABLE water_bodies ENABLE ROW LEVEL SECURITY;
CREATE POLICY water_bodies_anon_select ON water_bodies FOR SELECT TO anon          USING (true);
CREATE POLICY water_bodies_auth_select ON water_bodies FOR SELECT TO authenticated USING (true);
CREATE INDEX idx_water_bodies_geom  ON water_bodies USING GIST (geom);
CREATE INDEX idx_water_bodies_basin ON water_bodies (basin);

-- ── Concessions (Minerals Commission cadastre, weekly scrape) ────────────────
-- holder_name_normalised uses lower() only — unaccent() is STABLE not IMMUTABLE
-- and cannot live in a STORED generated column without a wrapper. Ghanaian
-- holder names are mostly ASCII; revisit if/when fuzzy news matching needs it.
CREATE TABLE concessions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cadastre_uid    TEXT UNIQUE NOT NULL,
  holder_name     TEXT NOT NULL,
  holder_name_normalised TEXT GENERATED ALWAYS AS (lower(holder_name)) STORED,
  license_no      TEXT,
  license_type    TEXT,
  license_status  TEXT,
  commodity       TEXT,
  region_id       INT REFERENCES regions(id)   ON DELETE SET NULL,
  district_id     INT REFERENCES districts(id) ON DELETE SET NULL,
  granted_at      DATE,
  expires_at      DATE,
  last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  pipeline_run_id BIGINT REFERENCES pipeline_runs(id) ON DELETE SET NULL,
  geom            GEOMETRY(MultiPolygon, 4326) NOT NULL,
  source_url      TEXT NOT NULL
);
ALTER TABLE concessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY concessions_anon_select ON concessions FOR SELECT TO anon          USING (true);
CREATE POLICY concessions_auth_select ON concessions FOR SELECT TO authenticated USING (true);
CREATE INDEX idx_concessions_geom               ON concessions USING GIST (geom);
CREATE INDEX idx_concessions_holder_normalised  ON concessions (holder_name_normalised);
CREATE INDEX idx_concessions_region_id          ON concessions (region_id);
CREATE INDEX idx_concessions_district_id        ON concessions (district_id);
CREATE INDEX idx_concessions_last_seen_at       ON concessions (last_seen_at DESC);
