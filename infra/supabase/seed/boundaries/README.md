# Boundaries Seed

Loads Ghana admin boundaries, forest reserves, and water bodies into the database.
Run once locally; production gets the same rows by applying migrations + this script.

## Data Sources

| Layer | Source | License |
|---|---|---|
| Regions (admin 1) | [GADM 4.1](https://gadm.org/download_country.html) — `gadm41_GHA_1.json` | Free for non-commercial research |
| Districts (admin 2) | [GADM 4.1](https://gadm.org/download_country.html) — `gadm41_GHA_2.json` | Free for non-commercial research |
| Water bodies | [OSM Overpass](https://overpass-api.de) — rivers/lakes with `waterway=river` or `natural=water` | ODbL |
| Forest reserves | [OSM Overpass](https://overpass-api.de) — `boundary=protected_area` clipped to Ghana | ODbL |

## Requirements

- `ogr2ogr` (GDAL): `sudo apt install gdal-bin` / `brew install gdal`
- `psql` connected to the target database
- `DATABASE_URL` environment variable set (port 5432, session mode)

## Usage

```bash
export DATABASE_URL="postgresql://postgres:password@localhost:5432/galamsey"
bash infra/supabase/seed/boundaries/seed.sh
```

The script is idempotent: rows are inserted with `ON CONFLICT DO NOTHING` so
re-running it after a partial failure is safe.

## File Layout

```
seed/boundaries/
  README.md      -- this file
  seed.sh        -- main entry point
  tmp/           -- downloaded data (gitignored)
```

## Manual Verification

```sql
SELECT count(*) FROM regions;          -- expect 16
SELECT count(*) FROM districts;        -- expect ~261
SELECT count(*) FROM forest_reserves;  -- expect >= 100
SELECT count(*) FROM water_bodies;     -- expect >= 5
```
