#!/usr/bin/env bash
# seed.sh — load Ghana boundaries (regions, districts, forest reserves, water bodies)
# Usage: DATABASE_URL=postgres://... bash seed.sh
# Idempotent: uses ON CONFLICT DO NOTHING throughout.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP="$SCRIPT_DIR/tmp"
mkdir -p "$TMP"

: "${DATABASE_URL:?DATABASE_URL must be set}"

PG="psql $DATABASE_URL --no-psqlrc --single-transaction --variable=ON_ERROR_STOP=1"
OGR="ogr2ogr -f PostgreSQL PG:\"$DATABASE_URL\" -t_srs EPSG:4326 -nlt MULTIPOLYGON -overwrite"

# ── Helpers ──────────────────────────────────────────────────────────────────

download_if_missing() {
  local url="$1" dest="$2"
  if [[ ! -f "$dest" ]]; then
    echo "Downloading $dest ..."
    curl -fsSL "$url" -o "$dest"
  else
    echo "Using cached $dest"
  fi
}

# ── 1. GADM 4.1 — Regions (admin level 1) ───────────────────────────────────
# GADM provides country-level GeoJSON downloads.
# File naming: gadm41_GHA_1.json  (ISO 3166-1 alpha-3 = GHA, level = 1)
GADM1="$TMP/gadm41_GHA_1.json"
download_if_missing \
  "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_GHA_1.json.zip" \
  "$TMP/gadm41_GHA_1.json.zip"

if [[ ! -f "$GADM1" ]]; then
  unzip -o "$TMP/gadm41_GHA_1.json.zip" -d "$TMP"
fi

echo "Loading regions ..."
$OGR -nln regions_staging "$GADM1"
$PG <<'SQL'
INSERT INTO regions (gid_1, name, geom, as_of, source_url)
SELECT
  "GID_1",
  "NAME_1",
  ST_Multi(wkb_geometry),
  '2024-01-01'::date,
  'https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_GHA_1.json.zip'
FROM regions_staging
ON CONFLICT (gid_1) DO NOTHING;
DROP TABLE IF EXISTS regions_staging;
SQL
echo "Regions loaded."

# ── 2. GADM 4.1 — Districts (admin level 2) ─────────────────────────────────
GADM2="$TMP/gadm41_GHA_2.json"
download_if_missing \
  "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_GHA_2.json.zip" \
  "$TMP/gadm41_GHA_2.json.zip"

if [[ ! -f "$GADM2" ]]; then
  unzip -o "$TMP/gadm41_GHA_2.json.zip" -d "$TMP"
fi

echo "Loading districts ..."
$OGR -nln districts_staging "$GADM2"
$PG <<'SQL'
INSERT INTO districts (gid_2, region_id, name, geom, as_of, source_url)
SELECT
  s."GID_2",
  r.id,
  s."NAME_2",
  ST_Multi(s.wkb_geometry),
  '2024-01-01'::date,
  'https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_GHA_2.json.zip'
FROM districts_staging s
JOIN regions r ON r.gid_1 = s."GID_1"
ON CONFLICT (gid_2) DO NOTHING;
DROP TABLE IF EXISTS districts_staging;
SQL
echo "Districts loaded."

# ── 3. OSM Overpass — Forest reserves (boundary=protected_area) ─────────────
# Query: all protected area relations within Ghana's bbox.
# bbox: [lon_min, lat_min, lon_max, lat_max] = [-3.26, 4.74, 1.19, 11.17]
RESERVES_QUERY='[out:json][timeout:120];
relation["boundary"="protected_area"](4.74,-3.26,11.17,1.19);
(._;>;);
out geom;'

RESERVES_OSM="$TMP/forest_reserves.geojson"
if [[ ! -f "$RESERVES_OSM" ]]; then
  echo "Fetching forest reserves from Overpass ..."
  curl -fsSL \
    --data-urlencode "data=$RESERVES_QUERY" \
    "https://overpass-api.de/api/interpreter" \
    -o "$TMP/reserves_raw.json"
  # Convert OSM JSON to GeoJSON using osmtogeojson (node) if available,
  # else fall back to the Python converter shipped with this repo.
  if command -v osmtogeojson &>/dev/null; then
    osmtogeojson "$TMP/reserves_raw.json" > "$RESERVES_OSM"
  else
    python3 - <<'PYEOF'
import json, sys

with open("'"$TMP"'/reserves_raw.json") as f:
    data = json.load(f)

features = []
for elem in data.get("elements", []):
    if elem.get("type") != "relation":
        continue
    name = elem.get("tags", {}).get("name", "Unnamed Reserve")
    # Build a rough bounding-box polygon from the member node coordinates
    coords = []
    for member in elem.get("members", []):
        if member.get("type") == "node" and "lat" in member and "lon" in member:
            coords.append([member["lon"], member["lat"]])
    if len(coords) < 4:
        continue
    features.append({
        "type": "Feature",
        "properties": {"name": name, "osm_id": elem["id"]},
        "geometry": {"type": "Polygon", "coordinates": [coords + [coords[0]]]}
    })

with open("'"$RESERVES_OSM"'", "w") as f:
    json.dump({"type": "FeatureCollection", "features": features}, f)

print(f"Converted {len(features)} protected area relations to GeoJSON")
PYEOF
  fi
fi

echo "Loading forest reserves ..."
$OGR -nln forest_reserves_staging "$RESERVES_OSM"
$PG <<'SQL'
DELETE FROM forest_reserves WHERE source = 'osm';
INSERT INTO forest_reserves (name, region_id, geom, as_of, source, source_url)
SELECT
  COALESCE(s.name, 'Unnamed Reserve'),
  (
    SELECT r.id FROM regions r
    WHERE ST_Intersects(r.geom, ST_Centroid(ST_Multi(s.wkb_geometry)))
    ORDER BY ST_Area(ST_Intersection(r.geom, ST_Multi(s.wkb_geometry))) DESC
    LIMIT 1
  ),
  ST_Multi(s.wkb_geometry),
  '2024-01-01'::date,
  'osm',
  'https://overpass-api.de'
FROM forest_reserves_staging s
WHERE ST_IsValid(s.wkb_geometry);
DROP TABLE IF EXISTS forest_reserves_staging;
SQL
echo "Forest reserves loaded."

# ── 4. OSM Overpass — Water bodies (rivers and lakes) ───────────────────────
WATER_QUERY='[out:json][timeout:120];
(
  relation["waterway"="river"](4.74,-3.26,11.17,1.19);
  relation["natural"="water"]["water"="lake"](4.74,-3.26,11.17,1.19);
  relation["natural"="water"]["water"="reservoir"](4.74,-3.26,11.17,1.19);
);
(._;>;);
out geom;'

WATER_OSM="$TMP/water_bodies.geojson"
if [[ ! -f "$WATER_OSM" ]]; then
  echo "Fetching water bodies from Overpass ..."
  curl -fsSL \
    --data-urlencode "data=$WATER_QUERY" \
    "https://overpass-api.de/api/interpreter" \
    -o "$TMP/water_raw.json"

  python3 - <<'PYEOF'
import json

with open("'"$TMP"'/water_raw.json") as f:
    data = json.load(f)

KIND_MAP = {"river": "river", "lake": "lake", "reservoir": "reservoir"}
features = []
for elem in data.get("elements", []):
    if elem.get("type") != "relation":
        continue
    tags = elem.get("tags", {})
    name = tags.get("name", "Unnamed")
    waterway = tags.get("waterway", "")
    water = tags.get("water", "")
    kind = KIND_MAP.get(waterway) or KIND_MAP.get(water) or "river"
    basin = tags.get("basin", None)

    coords = []
    for member in elem.get("members", []):
        if member.get("type") == "node" and "lat" in member and "lon" in member:
            coords.append([member["lon"], member["lat"]])
    if len(coords) < 4:
        continue

    props = {"name": name, "kind": kind}
    if basin:
        props["basin"] = basin
    features.append({
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "Polygon", "coordinates": [coords + [coords[0]]]}
    })

with open("'"$WATER_OSM"'", "w") as f:
    json.dump({"type": "FeatureCollection", "features": features}, f)

print(f"Converted {len(features)} water body relations to GeoJSON")
PYEOF
fi

echo "Loading water bodies ..."
$OGR -nln water_bodies_staging "$WATER_OSM"
$PG <<'SQL'
DELETE FROM water_bodies WHERE source_url = 'https://overpass-api.de';
INSERT INTO water_bodies (name, kind, basin, geom, as_of, source_url)
SELECT
  COALESCE(s.name, 'Unnamed'),
  COALESCE(s.kind, 'river'),
  NULLIF(s.basin, ''),
  ST_Multi(s.wkb_geometry),
  '2024-01-01'::date,
  'https://overpass-api.de'
FROM water_bodies_staging s
WHERE ST_IsValid(s.wkb_geometry);
DROP TABLE IF EXISTS water_bodies_staging;
SQL
echo "Water bodies loaded."

# ── Summary ──────────────────────────────────────────────────────────────────
$PG <<'SQL'
SELECT 'regions'         AS layer, count(*) FROM regions
UNION ALL
SELECT 'districts',                count(*) FROM districts
UNION ALL
SELECT 'forest_reserves',          count(*) FROM forest_reserves
UNION ALL
SELECT 'water_bodies',             count(*) FROM water_bodies;
SQL

echo ""
echo "Seed complete."
