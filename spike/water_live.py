"""Spike: water plant upstream clearing for the live site (six tiles, forest zone), next to the 15-tile figure.

Run from pipeline/ after a weekly run: uv run python ../spike/water_live.py
Writes the Pra basin upstream of Daboase, simplified, for the home page map to out/water/pra_basin.geojson.
"""
import datetime as dt
import json
import os
import sys

import geopandas as gpd
from shapely.geometry import Point

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from water import PLANTS, WORK_CRS, basins, clusters, upstream  # noqa: E402

from tracker import zone  # noqa: E402

OUT = os.path.join("out", "water")


def by_plant(pts: gpd.GeoDataFrame, b: gpd.GeoDataFrame) -> dict:
    joined = gpd.sjoin(pts, b[["HYBAS_ID", "geometry"]], predicate="within")
    ha_by_basin = joined.groupby("HYBAS_ID").ha.sum()
    result = {}
    for name, (river, lat, lon) in PLANTS.items():
        p = gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(WORK_CRS).iloc[0]
        start = b[b.distance(p) <= 2000].sort_values("UP_AREA", ascending=False).iloc[0]
        up = upstream(b, int(start.HYBAS_ID))
        result[name] = (river, float(ha_by_basin[ha_by_basin.index.isin(up)].sum()), up, float(start.UP_AREA))
    return result


def main():
    os.makedirs(OUT, exist_ok=True)
    b = basins().to_crs(WORK_CRS)
    live = gpd.read_file(os.path.join("out", "places", "latest.geojson")).to_crs(WORK_CRS)
    live_pts = gpd.GeoDataFrame(live[["ha"]], geometry=live.geometry.representative_point(), crs=WORK_CRS)
    wide = zone.inside(clusters(dt.date(2026, 10, 22)), zone.load())
    wide_pts = gpd.GeoDataFrame(wide[["ha"]], geometry=wide.geometry.representative_point(), crs=WORK_CRS)
    print(f"live: {len(live)} patches {live.ha.sum():,.0f} ha; 15 tiles in zone: {len(wide)} patches {wide.ha.sum():,.0f} ha")
    a, w = by_plant(live_pts, b), by_plant(wide_pts, b)
    for name in PLANTS:
        river, ha, up, area = a[name]
        print(f"{name} ({river}, {area:,.0f} km2 upstream): live {ha:,.0f} ha ({ha / live.ha.sum():.0%} of live), "
              f"15 tiles zoned {w[name][1]:,.0f} ha")
    up = a["Daboase"][2]
    pra = b[b.HYBAS_ID.isin(up)].union_all().simplify(500)
    gpd.GeoDataFrame({"name": ["Pra basin upstream of Daboase (HydroBASINS level 12)"]}, geometry=[pra],
                     crs=WORK_CRS).to_crs(4326).to_file(os.path.join(OUT, "pra_basin.geojson"), driver="GeoJSON",
                                                         COORDINATE_PRECISION=3)
    inside = gpd.sjoin(live_pts, gpd.GeoDataFrame(geometry=[pra], crs=WORK_CRS), predicate="within")
    print(f"Pra polygon written; {len(inside)} live patches inside it")
    json.dump({n: {"river": a[n][0], "live_ha": round(a[n][1]), "wide_ha": round(w[n][1]), "upstream_km2": round(a[n][3])}
               for n in PLANTS}, open(os.path.join(OUT, "plants.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
