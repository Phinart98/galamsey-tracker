# GFW Alerts Pipeline

Weekly ingest of [GFW integrated deforestation alerts][gfw-blog] (RADD + GLAD-L
+ GLAD-S2 + DIST-ALERT) for Ghana into the `alerts_gfw` table.

Runs every Sunday 02:00 UTC via GitHub Actions. Each run writes one row to
`pipeline_runs` for observability and is idempotent (`ON CONFLICT (alert_uid)
DO NOTHING`).

## What it ingests

For each alert pixel inside the Ghana bbox `(-3.26, 4.74, 1.20, 11.18)`:
latitude, longitude, alert date, confidence (low/high/highest/nominal), and
the source detector (radd/glad_l/glad_s2/dist_alert). The pipeline then calls
`alerts_gfw_join_admin(run_id)` to populate region/district/forest_reserve/
concession FKs in one scoped UPDATE.

## Setup

```bash
cd pipelines/gfw_alerts
uv sync --extra dev
```

You need a [GFW Data API key][gfw-key] (free, instant). Set:

```bash
export GFW_API_KEY=...
export DATABASE_URL=postgres://...   # port 5432, direct/session mode
```

## Usage

```bash
# Dry run: fetch + normalise, no writes (works without DATABASE_URL)
uv run python -m ingest --dry-run --max-pages 2

# Limit pages for smoke testing (the integrated dataset returns one page anyway)
uv run python -m ingest --max-pages 5

# Default window: last 14 days (overlap with prior run is absorbed by ON CONFLICT)
uv run python -m ingest

# Custom window: backfill a specific date range
uv run python -m ingest --from 2025-01-01 --to 2025-12-31
```

## Why the 14-day default window

Weekly cron + 14-day window guarantees no gap if a single run is skipped
(GitHub Actions cron can run up to ~30 min late). Re-fetching the prior week's
alerts is harmless because `alert_uid = md5(source:lon:lat:date)` makes them
identical to existing rows, and `ON CONFLICT (alert_uid) DO NOTHING` discards
the duplicates without touching the row.

## Verifying field names against the upstream API

The SQL query in `ingest.py` references two column aliases:
`gfw_integrated_alerts__date` and `gfw_integrated_alerts__confidence`.
The integrated dataset has no per-source field exposed via the raster
`/query` endpoint (detector provenance is implicit in the confidence value:
`highest` means detected by 2+ systems). Migration 0004 widens the source
CHECK to allow `'integrated'`, which is what this pipeline writes.

If GFW renames or restructures fields, get the canonical names from
<https://data-api.globalforestwatch.org/swagger> and update the SELECT clause
in `fetch_page()`.

[gfw-blog]: https://www.globalforestwatch.org/blog/data-and-tools/integrated-deforestation-alerts/
[gfw-key]: https://data-api.globalforestwatch.org/
