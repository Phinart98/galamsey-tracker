-- 0004_alerts_gfw_source_integrated.sql
-- The GFW integrated_alerts dataset has no per-source field exposed via the
-- raster /query endpoint -- detector provenance is implicit in the confidence
-- value (highest = detected by 2+ systems). 0003 hardcoded the source CHECK
-- to ('radd','glad_l','glad_s2','dist_alert'); this widens it to also accept
-- 'integrated', which is what the Phase 2 pipeline writes.
--
-- The per-source values remain valid for future phases that may query each
-- detector's dataset directly (e.g. Phase 3 SAR alerts from wur_radd_alerts).

ALTER TABLE alerts_gfw DROP CONSTRAINT alerts_gfw_source_check;
ALTER TABLE alerts_gfw ADD  CONSTRAINT alerts_gfw_source_check
  CHECK (source IN ('integrated', 'radd', 'glad_l', 'glad_s2', 'dist_alert'));
