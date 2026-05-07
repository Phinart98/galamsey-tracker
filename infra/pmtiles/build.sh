#!/usr/bin/env bash
# build.sh — export PostGIS layers -> GeoJSONSeq -> tippecanoe -> PMTiles
#
# Phase 1 delivery: copies output into apps/web/public/pmtiles/ so Vercel
# serves them as static assets. When R2 credentials are wired, the rclone
# section at the bottom takes over.
#
# Requirements: ogr2ogr (GDAL), tippecanoe, pmtiles CLI
#   macOS:  brew install gdal tippecanoe pmtiles
#   Linux:  see infra/pmtiles/Dockerfile for apt commands
#
# Usage:
#   DATABASE_URL=postgres://... bash infra/pmtiles/build.sh
#   # Optional R2 upload:
#   DATABASE_URL=... R2_BUCKET=galamsey-static bash infra/pmtiles/build.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TMP="$SCRIPT_DIR/tmp"
WEB_STATIC="$REPO_ROOT/apps/web/public/pmtiles"

mkdir -p "$TMP" "$WEB_STATIC"

: "${DATABASE_URL:?DATABASE_URL must be set}"

PG_DSN="PG:\"$DATABASE_URL\""

# ── 1. Export each layer as GeoJSONSeq ───────────────────────────────────────

echo "Exporting regions ..."
ogr2ogr -f GeoJSONSeq "$TMP/regions.geojsonl" "$PG_DSN" \
  -sql "SELECT id, gid_1, name, geom FROM regions" \
  -t_srs EPSG:4326 -lco RFC7946=YES

echo "Exporting districts ..."
ogr2ogr -f GeoJSONSeq "$TMP/districts.geojsonl" "$PG_DSN" \
  -sql "SELECT id, gid_2, name, region_id, geom FROM districts" \
  -t_srs EPSG:4326 -lco RFC7946=YES

echo "Exporting forest_reserves ..."
ogr2ogr -f GeoJSONSeq "$TMP/forest_reserves.geojsonl" "$PG_DSN" \
  -sql "SELECT id, name, area_ha, source, geom FROM forest_reserves" \
  -t_srs EPSG:4326 -lco RFC7946=YES

echo "Exporting water_bodies ..."
ogr2ogr -f GeoJSONSeq "$TMP/water_bodies.geojsonl" "$PG_DSN" \
  -sql "SELECT id, name, kind, basin, geom FROM water_bodies" \
  -t_srs EPSG:4326 -lco RFC7946=YES

echo "Exporting concessions ..."
ogr2ogr -f GeoJSONSeq "$TMP/concessions.geojsonl" "$PG_DSN" \
  -sql "SELECT id::text, cadastre_uid, holder_name, license_type, license_status, commodity, geom FROM concessions" \
  -t_srs EPSG:4326 -lco RFC7946=YES

# ── 2. Build boundaries PMTiles archive ─────────────────────────────────────

echo "Building boundaries.pmtiles ..."
tippecanoe \
  -o "$TMP/boundaries.pmtiles" \
  -L "regions:$TMP/regions.geojsonl" \
  -L "districts:$TMP/districts.geojsonl" \
  -L "forest_reserves:$TMP/forest_reserves.geojsonl" \
  -L "water_bodies:$TMP/water_bodies.geojsonl" \
  --force \
  --no-feature-limit \
  --no-tile-size-limit \
  -zg \
  --drop-densest-as-needed \
  --extend-zooms-if-still-dropping

# ── 3. Build concessions PMTiles archive ─────────────────────────────────────

echo "Building concessions.pmtiles ..."
tippecanoe \
  -o "$TMP/concessions.pmtiles" \
  -L "concessions:$TMP/concessions.geojsonl" \
  --force \
  --no-feature-limit \
  --no-tile-size-limit \
  -zg \
  --drop-densest-as-needed \
  --extend-zooms-if-still-dropping

# ── 4. Generate manifest.json (cache-busting) ────────────────────────────────

# sha256sum is GNU-only; shasum -a 256 is portable (macOS + Linux).
sha256() { shasum -a 256 "$1" 2>/dev/null || sha256sum "$1"; }
BOUNDARIES_SHA=$(sha256 "$TMP/boundaries.pmtiles"  | awk '{print $1}')
CONCESSIONS_SHA=$(sha256 "$TMP/concessions.pmtiles" | awk '{print $1}')
BUILT_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cat > "$TMP/manifest.json" <<JSON
{
  "built_at": "$BUILT_AT",
  "boundaries": {
    "path": "/pmtiles/boundaries.pmtiles",
    "sha256": "$BOUNDARIES_SHA"
  },
  "concessions": {
    "path": "/pmtiles/concessions.pmtiles",
    "sha256": "$CONCESSIONS_SHA"
  }
}
JSON

echo "Manifest:"
cat "$TMP/manifest.json"

# ── 5a. Copy to Vercel static assets (Phase 1 default) ───────────────────────

echo "Copying to apps/web/public/pmtiles/ ..."
cp "$TMP/boundaries.pmtiles"  "$WEB_STATIC/"
cp "$TMP/concessions.pmtiles" "$WEB_STATIC/"
cp "$TMP/manifest.json"       "$WEB_STATIC/"
echo "Static copy done. Files:"
ls -lh "$WEB_STATIC"

# ── 5b. R2 upload (optional — requires rclone + R2_BUCKET env var) ───────────

if [[ -n "${R2_BUCKET:-}" ]]; then
  echo "Uploading to R2 bucket: $R2_BUCKET ..."
  rclone copy "$TMP/boundaries.pmtiles"  "r2:${R2_BUCKET}/pmtiles/" --checksum --transfers=4
  rclone copy "$TMP/concessions.pmtiles" "r2:${R2_BUCKET}/pmtiles/" --checksum --transfers=4
  rclone copy "$TMP/manifest.json"       "r2:${R2_BUCKET}/pmtiles/" --checksum
  echo "R2 upload done."
fi

echo ""
echo "Build complete."
