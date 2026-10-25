"""How many towns and villages have land cleared within 1 km of them? (the "people living with it" angle)

Uses the active patches from the last weekly run and OpenStreetMap towns and villages over the enabled tiles.
OSM in rural Ghana misses many hamlets and some villages, so counts are a floor, not a census.

Run from the repo root: uv run --project pipeline python spike/towns_near.py
"""
import datetime as dt
import json
import os
import sys

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

sys.path.insert(0, "pipeline")
from tracker import places  # noqa: E402
from tracker.run import WORK_CRS, enabled_tiles  # noqa: E402

CACHE = "pipeline/out/cache/places"
RADIUS_M = 1000
tiles = enabled_tiles()
bounds = [t["bounds"] for t in tiles.values()]
bbox = (min(b[0] for b in bounds), min(b[1] for b in bounds), max(b[2] for b in bounds), max(b[3] for b in bounds))
covered = gpd.GeoSeries([box(*b) for b in bounds], crs=4326).union_all()

towns = places.settlements(CACHE)
towns = towns[towns.within(covered)].to_crs(WORK_CRS)
patches = gpd.read_file("pipeline/out/places/latest.geojson").to_crs(WORK_CRS)
index = json.load(open("pipeline/out/places/index.json", encoding="utf-8"))
patches["first_seen"] = patches["id"].map(lambda i: index.get(i, {}).get("first_seen"))
data_date = max(r["last_seen"] for r in index.values() if r.get("active"))
recent = str(dt.date.fromisoformat(data_date) - dt.timedelta(days=90))

ring = towns[["name", "place", "geometry"]].copy()
ring["geometry"] = ring.buffer(RADIUS_M)
hits = gpd.sjoin(patches[["id", "ha", "first_seen", "geometry"]], ring, predicate="intersects")
per = hits.groupby("index_right").agg(ha=("ha", "sum"), patches=("id", "nunique"),
                                      newest=("first_seen", "max")).join(towns[["name", "place"]])

print(f"OSM towns and villages inside the {len(tiles)} tiles: {len(towns)} "
      f"({(towns.place != 'village').sum()} towns or cities, {(towns.place == 'village').sum()} villages)")
print(f"with any patch within {RADIUS_M} m: {len(per)}")
for n in (5, 20, 50):
    print(f"  with at least {n} ha cleared within {RADIUS_M} m: {(per.ha >= n).sum()}")
print(f"  with clearing first seen in the last 90 days (since {recent}): {(per.newest >= recent).sum()}")
print(f"patches within {RADIUS_M} m of a named town or village: {hits.id.nunique()} of {len(patches)}"
      f" ({hits.id.nunique() / len(patches):.0%}), {patches[patches.id.isin(hits.id)].ha.sum():.0f} of {patches.ha.sum():.0f} ha")
print("\nMost cleared land within 1 km:")
print(per.sort_values("ha", ascending=False).head(15)[["name", "place", "ha", "patches", "newest"]].round(1).to_string())
per_tile = {t: int(towns.within(gpd.GeoSeries([box(*v["bounds"])], crs=4326).to_crs(WORK_CRS).iloc[0]).sum()) for t, v in tiles.items()}
print("\nOSM towns and villages per tile (a check on how complete OSM is):", per_tile)
os.makedirs("pipeline/out", exist_ok=True)
per.sort_values("ha", ascending=False).to_csv("pipeline/out/towns_near.csv")
pd.Series({"data_date": data_date}).to_json("pipeline/out/towns_near_meta.json")
