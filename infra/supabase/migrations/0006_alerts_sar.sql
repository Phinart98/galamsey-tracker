-- 0006_alerts_sar.sql
-- Sentinel-1 SAR backscatter-delta change detections, after Forkuor 2020.
-- See infra/supabase/migrations/README.md for schema conventions and the
-- Phase 3 plan at C:\Users\Philip\.claude\plans\galamsey-tracker-phase-swirling-stardust.md
-- for the algorithm and confidence rules.

-- ── alerts_sar ───────────────────────────────────────────────────────────────
-- One row per detected change polygon per detection period.
-- alert_uid = md5(period_start:sha256(wkb)[:16]) -- computed in pipelines/
-- sentinel1_sar/vectorise.py. ON CONFLICT DO NOTHING on re-ingest because a
-- (period, geometry) pair always denotes the same detection event.
CREATE TABLE alerts_sar (
  id                     BIGSERIAL PRIMARY KEY,
  alert_uid              TEXT UNIQUE NOT NULL,
  detection_period_start DATE NOT NULL,
  detection_period_end   DATE NOT NULL,
  area_ha                NUMERIC(10, 4) NOT NULL CHECK (area_ha > 0),
  delta_db_mean          NUMERIC(6, 3),
  delta_db_max           NUMERIC(6, 3),
  confidence             TEXT NOT NULL CHECK (confidence IN ('low', 'medium', 'high')),
  region_id              INT  REFERENCES regions(id)         ON DELETE SET NULL,
  district_id            INT  REFERENCES districts(id)       ON DELETE SET NULL,
  forest_reserve_id      INT  REFERENCES forest_reserves(id) ON DELETE SET NULL,
  concession_id          UUID REFERENCES concessions(id)     ON DELETE SET NULL,
  pipeline_run_id        BIGINT REFERENCES pipeline_runs(id) ON DELETE SET NULL,
  cog_url                TEXT,
  stac_item_id           TEXT,
  geom                   GEOMETRY(MultiPolygon, 4326) NOT NULL,
  ingested_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT alerts_sar_period_chk CHECK (detection_period_end >= detection_period_start)
);
ALTER TABLE alerts_sar ENABLE ROW LEVEL SECURITY;
CREATE POLICY alerts_sar_anon_select ON alerts_sar FOR SELECT TO anon          USING (true);
CREATE POLICY alerts_sar_auth_select ON alerts_sar FOR SELECT TO authenticated USING (true);

CREATE INDEX idx_alerts_sar_geom         ON alerts_sar USING GIST (geom);
CREATE INDEX idx_alerts_sar_period_conf  ON alerts_sar (detection_period_start DESC, confidence);
CREATE INDEX idx_alerts_sar_region       ON alerts_sar (region_id);
CREATE INDEX idx_alerts_sar_reserve      ON alerts_sar (forest_reserve_id) WHERE forest_reserve_id IS NOT NULL;
-- Partial index for the dashboard default ("only medium+ confidence on the map").
CREATE INDEX idx_alerts_sar_medium_high
  ON alerts_sar (detection_period_start DESC)
  WHERE confidence IN ('medium', 'high');

-- ── sar_alerts_join_admin ────────────────────────────────────────────────────
-- Called once per ingest run (NOT a row trigger). Scoped to pipeline_run_id so
-- cost is linear in new rows, not table size. Mirrors alerts_gfw_join_admin
-- from 0003, with ST_Intersects (polygons can straddle borders) instead of
-- ST_Contains (which is for points).
CREATE OR REPLACE FUNCTION sar_alerts_join_admin(run_id BIGINT)
RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
  -- All four admin joins use ST_Contains(admin.geom, ST_PointOnSurface(a.geom)):
  --   - GIST-accelerated; ~100x faster than ST_Area(ST_Intersection(...)) on
  --     detailed admin boundaries (the original implementation could exceed
  --     Supabase's statement_timeout on a full-Ghana run).
  --   - Deterministic for straddling polygons: ST_PointOnSurface returns a
  --     single representative point that's guaranteed to lie inside the
  --     polygon (unlike ST_Centroid which can fall outside for concave shapes).
  --     So a polygon overlapping two reserves always associates with exactly
  --     one, picked by where its representative point lands.
  --   - Consistent semantics across the 4 FKs: a polygon "belongs to" the
  --     admin unit its representative point falls into, full stop.
  UPDATE alerts_sar a
     SET region_id = r.id
    FROM regions r
   WHERE a.pipeline_run_id = run_id
     AND ST_Contains(r.geom, ST_PointOnSurface(a.geom));

  UPDATE alerts_sar a
     SET district_id = d.id
    FROM districts d
   WHERE a.pipeline_run_id = run_id
     AND ST_Contains(d.geom, ST_PointOnSurface(a.geom));

  UPDATE alerts_sar a
     SET forest_reserve_id = fr.id
    FROM forest_reserves fr
   WHERE a.pipeline_run_id = run_id
     AND ST_Contains(fr.geom, ST_PointOnSurface(a.geom));

  UPDATE alerts_sar a
     SET concession_id = c.id
    FROM concessions c
   WHERE a.pipeline_run_id = run_id
     AND ST_Contains(c.geom, ST_PointOnSurface(a.geom));
END;
$$;

-- ── sar_alerts_mvt (Martin function source) ──────────────────────────────────
-- SECURITY: callable by anon over the public Martin URL. Martin's PG connection
-- must use the anon role or a dedicated read-only role -- see
-- infra/cloudrun/martin/README.md.
--
-- query_params:
--   from / to      -- date range filter on detection_period_start (default: last 60 days)
--   min_confidence -- 'low' | 'medium' | 'high' (default: 'medium' for dashboard)
--
-- Why filter on detection_period_start (and not _end): the dashboard time
-- slider compares against the period a detection is FOR, not when it ran.
CREATE OR REPLACE FUNCTION sar_alerts_mvt(z INT, x INT, y INT, query_params JSON)
RETURNS BYTEA
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
  result        BYTEA;
  envelope_3857 GEOMETRY := ST_TileEnvelope(z, x, y);
  envelope_4326 GEOMETRY := ST_Transform(envelope_3857, 4326);
  v_from        DATE;
  v_to          DATE;
  v_minconf     TEXT;
BEGIN
  -- Defensively parse client-provided params: malformed values must fall back
  -- to defaults so a single bad request can't 500 the entire SAR layer for
  -- everyone (Martin would otherwise propagate the 500 to every tile).
  BEGIN
    v_from := COALESCE((query_params->>'from')::DATE, CURRENT_DATE - INTERVAL '60 days');
  EXCEPTION WHEN invalid_datetime_format OR datetime_field_overflow THEN
    v_from := (CURRENT_DATE - INTERVAL '60 days')::DATE;
  END;
  BEGIN
    v_to := COALESCE((query_params->>'to')::DATE, CURRENT_DATE);
  EXCEPTION WHEN invalid_datetime_format OR datetime_field_overflow THEN
    v_to := CURRENT_DATE;
  END;
  v_minconf := COALESCE(query_params->>'min_confidence', 'medium');
  -- Unknown min_confidence values silently degrade to 'medium' (matching the
  -- dashboard default) rather than the more dangerous "return everything" CASE
  -- fall-through, which would leak 'low' confidence noise to anyone with a
  -- typo in their tile URL.
  IF v_minconf NOT IN ('low', 'medium', 'high') THEN
    v_minconf := 'medium';
  END IF;
  WITH mvt AS (
    SELECT
      a.id,
      a.detection_period_start,
      a.area_ha,
      a.delta_db_mean,
      a.confidence,
      ST_AsMVTGeom(ST_Transform(a.geom, 3857), envelope_3857, 4096, 64, true) AS mvtgeom
    FROM alerts_sar a
    WHERE a.geom && envelope_4326
      AND a.detection_period_start BETWEEN v_from AND v_to
      AND CASE v_minconf
            WHEN 'high'   THEN a.confidence = 'high'
            WHEN 'medium' THEN a.confidence IN ('medium', 'high')
            ELSE TRUE
          END
  )
  SELECT ST_AsMVT(mvt, 'sar_alerts', 4096, 'mvtgeom') INTO result
  FROM mvt
  WHERE mvtgeom IS NOT NULL;
  RETURN result;
END;
$$;

GRANT EXECUTE ON FUNCTION sar_alerts_mvt(INT, INT, INT, JSON) TO anon, authenticated;
