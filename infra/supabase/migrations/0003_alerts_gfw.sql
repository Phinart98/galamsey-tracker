-- 0003_alerts_gfw.sql
-- GFW integrated deforestation alerts (RADD + GLAD-L + GLAD-S2 + DIST-ALERT).
-- See infra/supabase/migrations/README.md for schema conventions and
-- C:\Users\Philip\.claude\plans\galamsey-tracker-phase-radiant-pancake.md
-- for the Phase 2 design rationale (incl. why this table is NOT partitioned yet).

-- ── alerts_gfw ───────────────────────────────────────────────────────────────
-- Append-only event stream. One row per alert pixel.
-- alert_uid = md5(source:lon:lat:date) computed in the pipeline (matches
-- pipelines/concessions/scrape.py make_uid pattern); ON CONFLICT DO NOTHING
-- on re-ingest because alerts are events, not mutable facts.
CREATE TABLE alerts_gfw (
  id                BIGSERIAL PRIMARY KEY,
  alert_uid         TEXT UNIQUE NOT NULL,
  alert_date        DATE NOT NULL,
  source            TEXT NOT NULL CHECK (source IN ('radd', 'glad_l', 'glad_s2', 'dist_alert')),
  confidence        TEXT NOT NULL CHECK (confidence IN ('low', 'high', 'highest', 'nominal')),
  region_id         INT  REFERENCES regions(id)         ON DELETE SET NULL,
  district_id       INT  REFERENCES districts(id)       ON DELETE SET NULL,
  forest_reserve_id INT  REFERENCES forest_reserves(id) ON DELETE SET NULL,
  concession_id     UUID REFERENCES concessions(id)     ON DELETE SET NULL,
  pipeline_run_id   BIGINT REFERENCES pipeline_runs(id) ON DELETE SET NULL,
  geom              GEOMETRY(Point, 4326) NOT NULL,
  ingested_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE alerts_gfw ENABLE ROW LEVEL SECURITY;
CREATE POLICY alerts_gfw_anon_select ON alerts_gfw FOR SELECT TO anon          USING (true);
CREATE POLICY alerts_gfw_auth_select ON alerts_gfw FOR SELECT TO authenticated USING (true);

CREATE INDEX idx_alerts_gfw_geom        ON alerts_gfw USING GIST (geom);
CREATE INDEX idx_alerts_gfw_date_conf   ON alerts_gfw (alert_date DESC, confidence);
CREATE INDEX idx_alerts_gfw_region      ON alerts_gfw (region_id);
CREATE INDEX idx_alerts_gfw_source_date ON alerts_gfw (source, alert_date DESC);
-- Hot-path partial index for the "show only confirmed alerts" toggle.
CREATE INDEX idx_alerts_gfw_high_conf
  ON alerts_gfw (alert_date DESC)
  WHERE confidence IN ('high', 'highest');

-- ── ensure_alert_partitions (placeholder) ────────────────────────────────────
-- alerts_gfw is a single non-partitioned table at Phase 2. Promote this
-- function body and re-declare alerts_gfw as PARTITION BY RANGE (alert_date)
-- when row count crosses ~5M (~50 years at current Ghana volume).
-- The cron entry below preserves the CLAUDE.md contract so the upgrade can be
-- a body-only change without touching the schedule.
CREATE OR REPLACE FUNCTION ensure_alert_partitions(months_ahead INT DEFAULT 3)
RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
  RAISE NOTICE
    'alerts_gfw is not partitioned yet (months_ahead=%); '
    'upgrade migration 0003 to PARTITION BY RANGE before promoting this function',
    months_ahead;
END;
$$;

SELECT cron.schedule(
  'ensure-alert-partitions-monthly',
  '0 4 1 * *',
  $$SELECT ensure_alert_partitions(3)$$
);

-- ── alerts_gfw_join_admin ────────────────────────────────────────────────────
-- Called once per ingest run (NOT a row-level INSERT trigger -- that would
-- kill COPY-into-staging-then-INSERT throughput). Scoped to pipeline_run_id
-- so cost stays linear in new rows, not table size.
CREATE OR REPLACE FUNCTION alerts_gfw_join_admin(run_id BIGINT)
RETURNS void
LANGUAGE sql AS $$
  UPDATE alerts_gfw a SET
    region_id         = (SELECT id FROM regions         WHERE ST_Contains(geom, a.geom) LIMIT 1),
    district_id       = (SELECT id FROM districts       WHERE ST_Contains(geom, a.geom) LIMIT 1),
    forest_reserve_id = (SELECT id FROM forest_reserves WHERE ST_Contains(geom, a.geom) LIMIT 1),
    concession_id     = (SELECT id FROM concessions     WHERE ST_Contains(geom, a.geom) LIMIT 1)
  WHERE a.pipeline_run_id = run_id;
$$;

-- ── gfw_alerts_mvt (Martin function source) ──────────────────────────────────
-- SECURITY: This function is callable by anon over the public Martin URL.
-- Martin's PG connection MUST use the anon role (or a dedicated martin_reader),
-- never service_role -- otherwise public requests inherit service-role privileges
-- and the alerts table can be drained from the open internet.
-- Signature (z, x, y, query_params json) matches Martin v0.13+ auto-discovery.
CREATE OR REPLACE FUNCTION gfw_alerts_mvt(z INT, x INT, y INT, query_params JSON)
RETURNS BYTEA
LANGUAGE plpgsql STABLE PARALLEL SAFE AS $$
DECLARE
  result        BYTEA;
  envelope_3857 GEOMETRY := ST_TileEnvelope(z, x, y);              -- MVT tiles are in 3857
  envelope_4326 GEOMETRY := ST_Transform(envelope_3857, 4326);     -- alerts_gfw.geom is in 4326
  v_from        DATE     := COALESCE((query_params->>'from')::DATE, CURRENT_DATE - INTERVAL '30 days');
  v_to          DATE     := COALESCE((query_params->>'to')::DATE,   CURRENT_DATE);
  v_minconf     TEXT     := COALESCE(query_params->>'min_confidence', 'low');
BEGIN
  WITH mvt AS (
    SELECT
      a.id,
      a.alert_date,
      a.source,
      a.confidence,
      ST_AsMVTGeom(ST_Transform(a.geom, 3857), envelope_3857, 4096, 64, true) AS mvtgeom
    FROM alerts_gfw a
    WHERE a.geom && envelope_4326                          -- GIST-friendly: same SRID as the index
      AND a.alert_date BETWEEN v_from AND v_to
      AND CASE v_minconf
            WHEN 'high'    THEN a.confidence IN ('high', 'highest')
            WHEN 'highest' THEN a.confidence = 'highest'
            ELSE TRUE
          END
  )
  SELECT ST_AsMVT(mvt, 'gfw_alerts', 4096, 'mvtgeom') INTO result
  FROM mvt
  WHERE mvtgeom IS NOT NULL;                               -- ST_AsMVTGeom returns NULL outside the envelope
  RETURN result;
END;
$$;

GRANT EXECUTE ON FUNCTION gfw_alerts_mvt(INT, INT, INT, JSON) TO anon, authenticated;
