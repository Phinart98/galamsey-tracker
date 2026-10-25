"""Dry-season river colour (NDTI) per 10 km reach from Sentinel-2 L2A water pixels.

NDTI = (red - green) / (red + green): higher means browner, sediment-laden water.
Only pixels the L2A scene classification calls water (SCL=6) count, so banks and
clouds are excluded. Reflectance uses each asset's scale/offset (baseline 04.00+
scenes from 2022 carry a -0.1 offset that would otherwise fake a colour change).
"""
import sys, time, numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio.warp import transform as warp_xy
from shapely.geometry import shape
from pystac_client import Client

river, seasons = sys.argv[1], sys.argv[2:]          # e.g. Pra 2016 2019 2022 2025 (season = Nov y .. Mar y+1)
line = gpd.read_file("data/osm/rivers.gpkg").query("river == @river").to_crs(32630).geometry.iloc[0]
parts = list(getattr(line, "geoms", [line]))
pts, reach = [], []
offset_km = 0.0
for part in parts:
    for d in np.arange(0, part.length, 100):
        pts.append(part.interpolate(d)); reach.append(int((offset_km + d / 1000) // 10))
    offset_km += part.length / 1000
pts_ll = gpd.GeoSeries(pts, crs=32630).to_crs(4326)
lons, lats = pts_ll.x.values, pts_ll.y.values
bbox = [lons.min(), lats.min(), lons.max(), lats.max()]
cat = Client.open("https://earth-search.aws.element84.com/v1")

def scaled(item, key, raw):
    rb = (item.assets[key].extra_fields.get("raster:bands") or [{}])[0]
    return raw * rb.get("scale", 1e-4) + rb.get("offset", 0.0)

rows = []
for y in map(int, seasons):
    t0 = time.time()
    items = [i for c in ["sentinel-2-c1-l2a", "sentinel-2-l2a"]
             for i in cat.search(collections=[c], bbox=bbox, datetime=f"{y}-11-01/{y+1}-03-31",
                                 query={"eo:cloud_cover": {"lt": 40}}, max_items=200).items()]
    by_tile = {}
    for it in sorted(items, key=lambda i: i.properties["eo:cloud_cover"]):
        tile = it.properties.get("grid:code") or it.id.split("_")[1]
        by_tile.setdefault(tile, [])
        if len(by_tile[tile]) < 4 and not any(abs((it.datetime - o.datetime).days) < 1 for o in by_tile[tile]):
            by_tile[tile].append(it)
    for tile, its in by_tile.items():
        for it in its:
            fp = shape(it.geometry)
            idx = [k for k in range(len(pts)) if fp.contains(pts_ll.iloc[k])]
            if not idx:
                continue
            vals = {}
            for key in ("red", "green", "scl"):
                with rasterio.open(it.assets[key].href) as src:
                    xs, ys = warp_xy("EPSG:4326", src.crs, lons[idx].tolist(), lats[idx].tolist())
                    if key == "scl":  # 20 m band
                        vals[key] = np.array([v[0] for v in src.sample(zip(xs, ys))])
                    else:
                        vals[key] = scaled(it, key, np.array([v[0] for v in src.sample(zip(xs, ys))], float))
            water = vals["scl"] == 6
            ndti = (vals["red"] - vals["green"]) / (vals["red"] + vals["green"] + 1e-9)
            for k, w, v in zip(idx, water, ndti):
                if w:
                    rows.append((y, reach[k], it.datetime.date(), v))
    print(f"season {y}/{y+1}: {sum(len(v) for v in by_tile.values())} scenes, {time.time()-t0:.0f}s", flush=True)

df = pd.DataFrame(rows, columns=["season", "reach", "date", "ndti"])
df.to_csv(f"data/river_{river}.csv", index=False)
tab = df.groupby(["reach", "season"]).ndti.median().unstack().round(3)
n = df.groupby(["reach", "season"]).ndti.size().unstack()
print("\nMedian NDTI per 10 km reach (rows) per dry season (cols); higher = browner")
print(tab.to_string())
print("\nwater samples per cell:\n", n.fillna(0).astype(int).to_string())
