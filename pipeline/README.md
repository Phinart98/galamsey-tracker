# Pipeline

Weekly job that turns NASA and Copernicus satellite data into the numbers and images on the site.

## What it does

| Command | Output |
|---|---|
| `uv run python -m tracker.run weekly` | Finds land that lost most of its plant cover in the last 12 months (NASA OPERA DIST-ALERT, patches of at least 1 ha), checks each patch against the Minerals Commission's active licences, names it after the nearest town and district, and gives it a permanent id. Writes `data/summary/latest.json`, `data/summary/YYYY-MM.json` , `data/places/aliases.json` and `data/towns.json` (towns and villages with cleared land within 1 km). The summary also gives the clearing upstream of each water treatment plant (`water_plants.geojson`). |
| `uv run python -m tracker.run chips --limit 80` | Makes before/after Sentinel-2 images (AVIF and WebP, 360 and 720 px) for places of at least 3 ha that do not have them yet. Skips any image with more than 10% cloud. |
| `uv run python -m tracker.run trend` | Adds one point per month to `data/trend.json`: hectares cleared in the 12 months to the 22nd, by licence class. The same date every month keeps the comparison fair. NASA confirms loss weeks after first seeing it, so each point combines readings from that day and 2 and 4 months later. Until the last reading exists the point is marked provisional and is recomputed each run. |

Every run updates `data/status.json`, including when it fails, so the site can say when data is late.

Files in `data/` are small and committed. Larger files (the places index, patch shapes, seeds and images) go in `pipeline/out/` and are synced to Cloudflare R2 under `v1/`.

## Coverage

Only tiles listed with `"enabled": true` in `tiles.json` are processed. Before a tile is switched on, a random sample of about 20 patches is checked by eye with before/after images, and the result is recorded in `tiles.json`. The method and its known limits are in `docs/validation/2026-10-data-spike.md`.

## Running locally

```bash
cd pipeline
uv sync --extra dev
uv run pytest
uv run python -m tracker.run weekly
```

You need a free NASA Earthdata account in `~/.netrc` (Windows: `~/_netrc`):

```
machine urs.earthdata.nasa.gov login YOUR_USERNAME password YOUR_PASSWORD
```

## GitHub secrets for the weekly workflow

`EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`.

## Data sources and licences

- NASA OPERA DIST-ALERT-HLS (public domain, NASA)
- Copernicus Sentinel-2 via Earth Search (Copernicus open licence; images credited "Contains modified Copernicus Sentinel data")
- Minerals Commission cadastre, ghana.revenuedev.org (used to classify licence type only; boundaries and holder names are not republished)
- geoBoundaries Ghana districts (CC BY 4.0) and OpenStreetMap places (ODbL)
