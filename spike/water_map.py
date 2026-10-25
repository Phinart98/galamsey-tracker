"""The base map for the home page water section: land, the Pra catchment and the main rivers.

Writes apps/site/src/data/water-map.json (lon/lat, 3 decimals). The site draws it as SVG at build time and adds
the clearing from the weekly data. Sources: geoBoundaries GHA districts (land, CC BY 4.0), HydroBASINS catchments
via pipeline/water_plants.geojson, HydroRIVERS v1.0 (Lehner and Grill 2013) for rivers draining at least 800 km2.

Needs pipeline/out/cache/hydro/rivers/HydroRIVERS_v10_af_shp.zip
(https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_af_shp.zip).
Run from pipeline/: uv run python ../spike/water_map.py
"""
import json
import os

import geopandas as gpd
from shapely.geometry import box, mapping
from shapely.ops import linemerge, unary_union

FRAME = (-3.1, 4.75, -0.1, 7.35)
WORK_CRS = "EPSG:32630"
MIN_UPLAND_KM2 = 800
OUT = os.path.join("..", "apps", "site", "src", "data", "water-map.json")

frame = box(*FRAME)
land = gpd.read_file("out/cache/places/districts.geojson").to_crs(WORK_CRS).union_all().simplify(400)
land = gpd.GeoSeries([land], crs=WORK_CRS).to_crs(4326).iloc[0].intersection(frame)
plants = gpd.read_file("water_plants.geojson")
pra = plants[plants.plant == "Daboase"].iloc[0]
RIVERS = "out/cache/hydro/rivers/HydroRIVERS_v10_af_shp.zip"
if os.path.exists(RIVERS):
    rivers = gpd.read_file(f"zip://{RIVERS}!HydroRIVERS_v10_af_shp/HydroRIVERS_v10_af.shp", bbox=FRAME)
    rivers = rivers[rivers.UPLAND_SKM >= MIN_UPLAND_KM2].clip(frame).to_crs(WORK_CRS)
    rivers["geometry"] = rivers.simplify(400)
    rivers = rivers.to_crs(4326)
else:
    print("no HydroRIVERS file: writing the map without rivers")
    rivers = gpd.GeoDataFrame({"UPLAND_SKM": []}, geometry=[], crs=4326)
pra_area = pra.geometry.buffer(0.01)


def coords(geom):
    def r(c):
        return [[round(x, 3), round(y, 3)] for x, y in c]
    m = mapping(geom)
    if m["type"] == "Polygon":
        return [[r(ring) for ring in m["coordinates"]]]
    if m["type"] == "MultiPolygon":
        return [[r(ring) for ring in poly] for poly in m["coordinates"]]
    if m["type"] == "LineString":
        return [r(m["coordinates"])]
    return [r(line) for line in m["coordinates"]]


# One merged line per stroke width and catchment, so the SVG has a few paths rather than hundreds of reaches
rivers["cls"] = rivers.UPLAND_SKM.map(lambda a: 8000 if a >= 8000 else 2000 if a >= 2000 else MIN_UPLAND_KM2)
rivers["in_pra"] = rivers.geometry.within(pra_area)
rivers_out = [{"km2": int(cls), "pra": bool(in_pra), "lines": coords(linemerge(unary_union(list(g.geometry))))}
              for (cls, in_pra), g in rivers.groupby(["cls", "in_pra"]) if len(g)]

out = {
    "frame": FRAME,
    "land": coords(land),
    "pra": coords(pra.geometry.intersection(frame)),
    "plant": {"name": "Daboase", "lon": pra.plant_lon, "lat": pra.plant_lat},
    "rivers": rivers_out,
    "credit": "Land: geoBoundaries. Rivers and catchment: HydroSHEDS (Lehner and Grill 2013).",
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(out, open(OUT, "w"), separators=(",", ":"))
print(len(rivers), "river reaches in", len(rivers_out), "paths,", os.path.getsize(OUT) // 1024, "KB")
