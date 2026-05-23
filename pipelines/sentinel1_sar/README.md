# Sentinel-1 SAR change detection pipeline

Monthly cron that detects newly cleared land in Ghana using Sentinel-1 RTC
backscatter time-series. Adapts Forkuor et al. 2020 (MDPI Remote Sensing
12(6):911) for monthly operational use: trailing-12-month baseline, +1.65 dB
threshold on both VV and VH polarisations, polygon vectorisation, R2 + PostGIS
publish.

## What it produces

Per run:

1. A 3-band Cloud Optimised GeoTIFF at
   `r2://galamsey-static/cog/sentinel1/{YYYY-MM}.tif`
   (band 1: delta VV dB, band 2: delta VH dB, band 3: binary mask)
2. A STAC Item at
   `r2://galamsey-static/cog/sentinel1/items/{YYYY-MM}.json`
   appended to the collection catalog at
   `r2://galamsey-static/cog/sentinel1/catalog.json`
3. ~50-500 rows in `alerts_sar` keyed by `alert_uid = md5(period:wkb_sha)`,
   with `region_id` / `district_id` / `forest_reserve_id` / `concession_id`
   populated by `sar_alerts_join_admin`.

## Run locally

```bash
cd pipelines/sentinel1_sar

# One-time: install deps. ~90s on Linux with prebuilt wheels; on Windows use WSL2.
uv sync --extra dev

# Copy and fill in secrets
cp .env.example .env
# edit .env

# Dry-run on a single hotspot (no R2 writes, no DB writes). ~3-5 min.
set -a; source .env; set +a
uv run python -m detect --aoi wassa --period 2026-04 --dry-run

# Real run on a single hotspot. ~5-10 min, ~20 MB COG, ~100-300 polygons.
uv run python -m detect --aoi wassa --period 2026-04

# Full Ghana monthly run. ~60-120 min on a 16 GB RAM machine.
uv run python -m detect --period 2026-04
```

## CLI

```
uv run python -m detect [OPTIONS]

  --period YYYY-MM     Detection period (default: previous calendar month)
  --aoi {ghana|wassa|atewa|birim|tano|pra}
                       AOI bbox (default: ghana). Smaller AOIs are for local
                       testing. Pipeline cron always uses ghana.
  --baseline-months N  Trailing baseline window (default: 12)
  --threshold-db F     Backscatter delta threshold in dB (default: 1.65)
  --min-area-ha F      Drop polygons below this area (default: 0.5)
  --dry-run            Compute everything but skip R2 + DB writes
```

## Algorithm (Forkuor 2020 adaptation)

```
For each pixel in the AOI:
  baseline_VV = mean(VV_dB) over (period_start - baseline_months, period_start)
  baseline_VH = mean(VH_dB) over (period_start - baseline_months, period_start)
  current_VV  = mean(VV_dB) over (period_start, period_end)
  current_VH  = mean(VH_dB) over (period_start, period_end)
  delta_VV    = current_VV - baseline_VV
  delta_VH    = current_VH - baseline_VH
  mask        = (delta_VV >= 1.65) AND (delta_VH >= 1.65)

Vectorise mask, simplify (50m tolerance), drop area < 0.5 ha.

Confidence per polygon:
  high   if within 500 m of a mapped water body OR inside a forest reserve
  low    if area < 1 ha OR delta_dB mean < 2 dB
  medium otherwise
```

Why both bands: Forkuor showed VV alone over-detects flooded paddy / wetland;
VH alone misses dry-season clearings. The joint mask eliminates ~80% of false
positives.

Why trailing 12-month baseline: averages a full year so seasonal vegetation
variation cancels out. The paper used 5-year baselines for stronger long-term
signal but a monthly operational pipeline needs sensitivity to *recent* change.

## Known false positives

- Rice paddies in northern Ghana during transplanting (Mar-May) -- standing
  water + bare soil mix raises VV. Mitigation: log-scale flood fraction
  threshold added in 0006 migration's `confidence` rule -- pixels with very
  high VV delta but low VH delta are downgraded.
- Urban edges where new construction lays bare earth. Galamsey-focused AOI
  buffers exclude major town footprints; full-Ghana run will return some
  spurious hits in Kumasi/Accra suburbs.
- Harvested oil palm plantations in the Western Region. Distinguishable from
  galamsey only via concession overlay (legal harvest = registered concession).
  Phase 5+ citizen reports will help ground-truth these.

## See also

- `docs/methodology/sentinel1-detection.md` -- the public-facing reproducibility doc.
- `infra/supabase/migrations/0006_alerts_sar.sql` -- the schema this pipeline writes into.
- `pipelines/gfw_alerts/ingest.py` -- the structural template this pipeline follows.
