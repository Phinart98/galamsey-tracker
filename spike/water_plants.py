"""The catchment upstream of each water treatment plant, as a small file for the pipeline (tracker/water.py).

Every HydroBASINS level 12 basin (Lehner and Grill 2013) upstream of each plant (spike log s16), merged and
simplified to about 200 m. Needs the HydroBASINS Africa level 12 zip in pipeline/out/cache/hydro (see water.py).

Run from pipeline/: uv run python ../spike/water_plants.py
"""
import os
import sys

import geopandas as gpd
from shapely.geometry import Point

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from water import PLANTS, WORK_CRS, basins, upstream  # noqa: E402

b = basins().to_crs(WORK_CRS)
rows = []
for name, (river, lat, lon) in PLANTS.items():
    p = gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(WORK_CRS).iloc[0]
    start = b[b.distance(p) <= 2000].sort_values("UP_AREA", ascending=False).iloc[0]
    up = b[b.HYBAS_ID.isin(upstream(b, int(start.HYBAS_ID)))]
    rows.append({"plant": name, "river": river, "plant_lat": lat, "plant_lon": lon,
                 "upstream_km2": round(float(start.UP_AREA)), "geometry": up.union_all().simplify(200)})
out = gpd.GeoDataFrame(rows, crs=WORK_CRS).to_crs(4326)
out.to_file("water_plants.geojson", driver="GeoJSON", COORDINATE_PRECISION=4)
print(out.drop(columns="geometry").to_string(), os.path.getsize("water_plants.geojson") // 1024, "KB")
