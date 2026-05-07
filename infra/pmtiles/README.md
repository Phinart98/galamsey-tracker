# PMTiles Build

Exports PostGIS boundary and concession layers to `.pmtiles` archives
using `ogr2ogr` + `tippecanoe`.

## Output

| File | Layers | Use |
|---|---|---|
| `boundaries.pmtiles` | regions, districts, forest_reserves, water_bodies | Static reference overlays |
| `concessions.pmtiles` | concessions | Weekly-refreshed cadastre polygons |
| `manifest.json` | — | SHA256 hashes + build timestamp for cache busting |

## Phase 1 delivery

Files are copied to `apps/web/public/pmtiles/` and served by Vercel as
static assets. No R2 bucket required.

## Phase 2+ delivery (R2)

Set the `R2_BUCKET` environment variable to upload via `rclone`:

```bash
DATABASE_URL=postgres://... R2_BUCKET=galamsey-static bash infra/pmtiles/build.sh
```

Configure rclone with `rclone config` before running (provider: Cloudflare R2,
access_key_id + secret_access_key from R2 API tokens).

## Local requirements

- `ogr2ogr` (GDAL): `brew install gdal` or `sudo apt install gdal-bin`
- `tippecanoe`: `brew install tippecanoe` or build from [source](https://github.com/felt/tippecanoe)
- `pmtiles` CLI (optional, for inspection): `brew install pmtiles`
- `rclone` (optional, for R2 upload): `brew install rclone`

## Usage

```bash
DATABASE_URL=postgres://user:pass@host:5432/dbname bash infra/pmtiles/build.sh
```

## CI/CD

Use the `infra/pmtiles/Dockerfile` for a reproducible build environment
(GDAL 3.9 + tippecanoe + rclone pre-installed).

## Verifying output

```bash
# Inspect layers and tile count
pmtiles show apps/web/public/pmtiles/boundaries.pmtiles
pmtiles show apps/web/public/pmtiles/concessions.pmtiles

# Preview in browser
# Open https://pmtiles.io and drag the .pmtiles file onto the map
```
