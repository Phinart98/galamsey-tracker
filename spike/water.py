"""Spike: hectares cleared in the last 12 months upstream of the water treatment plants that supply cities.

Run from pipeline/ (uses the tracker package):
    uv run python ../spike/water.py

Basins: HydroBASINS level 12 (Lehner and Grill 2013). Plants: OpenStreetMap man_made=water_works.
A plant is snapped to the basin within 2 km that drains the largest area, because a mapped plant
usually sits beside its intake rather than on the river.
"""
import datetime as dt
import os
import zipfile
from collections import defaultdict

import geopandas as gpd
from shapely.geometry import Point

from tracker import nasa
from tracker.dist import cluster_polygons, loss_mask
from tracker.identity import dedupe_tiles

PIPELINE = os.path.dirname(os.path.abspath(__file__)).replace("spike", "pipeline")
HYDRO = os.path.join(PIPELINE, "out", "cache", "hydro")
CLUSTERS = os.path.join(PIPELINE, "out", "cache", "clusters")
WORK_CRS = "EPSG:32630"
TILES = ["T30NVM", "T30NVN", "T30NWL", "T30NWM", "T30NWN", "T30NWP", "T30NXL", "T30NXM", "T30NXN",
         "T30NXP", "T30NYL", "T30NYM", "T30NYN", "T30NZM", "T30NZN"]
PLANTS = {  # name, river, lat, lon (OSM, checked 2026-10-25)
    "Weija": ("Densu", 5.5813, -0.3370),
    "Kwanyako": ("Ayensu", 5.3675, -0.6190),
    "Daboase": ("Pra", 5.1412, -1.6561),
    "Barekese": ("Offin", 6.8300, -1.7214),
    "Owabi": ("Owabi", 6.7487, -1.7027),
}


def basins() -> gpd.GeoDataFrame:
    shp = os.path.join(HYDRO, "hybas_af_lev12_v1c.shp")
    if not os.path.exists(shp):
        with zipfile.ZipFile(os.path.join(HYDRO, "hybas_af_lev12.zip")) as z:
            z.extractall(HYDRO)
    return gpd.read_file(shp, bbox=(-4.0, 4.3, 2.0, 11.5))


def clusters(day: dt.date) -> gpd.GeoDataFrame:
    os.makedirs(CLUSTERS, exist_ok=True)
    found = nasa.latest_per_tile("-3.9,4.4,0.8,8.2", day, lookback_days=20)
    parts = []
    for t in TILES:
        path = os.path.join(CLUSTERS, f"{t}-{day}.gpkg")
        if not os.path.exists(path):
            e = found[t]
            st, dd, tr, crs = nasa.read_status_and_date(e)
            g = cluster_polygons(loss_mask(st, dd, nasa.acquired(e["title"])), dd, tr, crs).to_crs(WORK_CRS)
            g["tile"] = t
            g.to_file(path, driver="GPKG")
            print(f"  {t}: {len(g)} patches", flush=True)
        parts.append(gpd.read_file(path))
    return dedupe_tiles(parts)


def upstream(b: gpd.GeoDataFrame, start: int) -> set[int]:
    feeders = defaultdict(list)
    for hid, down in zip(b.HYBAS_ID, b.NEXT_DOWN):
        feeders[down].append(hid)
    seen, todo = {start}, [start]
    while todo:
        for f in feeders[todo.pop()]:
            if f not in seen:
                seen.add(f)
                todo.append(f)
    return seen


def main():
    b = basins().to_crs(WORK_CRS)
    c = clusters(dt.date(2026, 10, 22))
    pts = gpd.GeoDataFrame(c[["ha"]], geometry=c.geometry.representative_point(), crs=WORK_CRS)
    print(f"patches {len(c)}, {round(c.ha.sum())} ha across {len(TILES)} tiles (overlaps removed)")
    joined = gpd.sjoin(pts, b[["HYBAS_ID", "geometry"]], predicate="within")
    ha_by_basin = joined.groupby("HYBAS_ID").ha.sum()
    for name, (river, lat, lon) in PLANTS.items():
        p = gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(WORK_CRS).iloc[0]
        near = b[b.distance(p) <= 2000]
        start = near.sort_values("UP_AREA", ascending=False).iloc[0]
        up = upstream(b, int(start.HYBAS_ID))
        ups = b[b.HYBAS_ID.isin(up)]
        ha = float(ha_by_basin[ha_by_basin.index.isin(up)].sum())
        print(f"{name} ({river}): upstream {start.UP_AREA:,.0f} km2 in {len(up)} basins, "
              f"cleared {ha:,.0f} ha; upstream extent lon {ups.to_crs(4326).total_bounds.round(2)}")


if __name__ == "__main__":
    main()
