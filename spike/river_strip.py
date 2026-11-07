"""s35: the Pra "unrolled", a straight strip of satellite pictures from Twifo Praso down to the Daboase plant.

The river's course (HydroRIVERS main stem, smoothed) is walked every 10 m; at each step a line across the river,
STRIP_HALF_M either side, is sampled from Sentinel-2 crops. Side by side the steps make one long straight picture,
upstream on the left, the plant on the right. Two rows: an early dry season (2016-2018) and the newest one.
Also writes the towns and cleared patches along the way, with their distance downstream, for the prototype page.

Run from the repo root: uv run --project pipeline python spike/river_strip.py
"""
import datetime as dt
import json
import os
import sys
import time

import geopandas as gpd
import numpy as np
from PIL import Image
from shapely.geometry import LineString, Point
from shapely.ops import linemerge

sys.path.insert(0, "pipeline")
from tracker import chips  # noqa: E402

RIVERS = "pipeline/out/cache/hydro/rivers/HydroRIVERS_v10_af_shp.zip"
START = (-1.548, 5.612)    # Twifo Praso bridge
END = (-1.6561, 5.1412)    # Daboase plant
STEP_M = 10
STRIP_HALF_M = 1000
CHUNK_M = 2500             # one Sentinel-2 crop serves this much river
CROP_HALF_KM = 1.9         # big enough to hold the strip around a chunk even where the river bends
EPOCHS = {"then": (dt.date(2016, 11, 1), dt.date(2018, 3, 31)), "now": (dt.date(2025, 11, 1), dt.date(2026, 3, 15))}
CRS = 32630
OUT = "pipeline/out/checks/strip"
os.makedirs(OUT, exist_ok=True)


def course():
    r = gpd.read_file(f"zip://{RIVERS}!HydroRIVERS_v10_af_shp/HydroRIVERS_v10_af.shp", bbox=(-1.9, 5.0, -1.3, 5.8)).to_crs(CRS)
    start = gpd.GeoSeries([Point(START)], crs=4326).to_crs(CRS).iloc[0]
    end = gpd.GeoSeries([Point(END)], crs=4326).to_crs(CRS).iloc[0]
    big = r[r.UPLAND_SKM > 15000]
    reach = big.loc[big.distance(start).idxmin()]
    by_id = r.set_index("HYRIV_ID")
    parts, rid = [], reach.HYRIV_ID
    while rid in by_id.index:
        parts.append(by_id.loc[rid].geometry)
        if by_id.loc[rid].geometry.distance(end) < 1500:
            break
        rid = by_id.loc[rid].NEXT_DOWN
    line = linemerge(parts)
    line = LineString(list(line.coords)) if line.geom_type == "LineString" else LineString([c for g in line.geoms for c in g.coords])
    a, b = line.project(start), line.project(end)
    line = LineString([line.interpolate(d).coords[0] for d in np.arange(a, b, 50)])
    # Smooth the 500 m HydroRIVERS course so the strip does not kink: a running mean over 1 km
    xy = np.array(line.coords)
    k = 21
    pad = np.pad(xy, ((k // 2, k // 2), (0, 0)), mode="edge")
    smooth = np.stack([np.convolve(pad[:, i], np.ones(k) / k, mode="valid") for i in (0, 1)], axis=1)
    return LineString(smooth)


def tried(fn, *args, attempts=4):
    for a in range(attempts):
        try:
            return fn(*args)
        except Exception as e:  # noqa: BLE001  slow link drops
            print("   retry", type(e).__name__, flush=True)
            time.sleep(20 * (a + 1))
    return None


def strip(line, epoch):
    start, end = EPOCHS[epoch]
    n = int(line.length // STEP_M)
    rows = int(2 * STRIP_HALF_M // STEP_M)
    img = np.full((rows, n, 3), 235, np.uint8)
    to_ll = gpd.GeoSeries(crs=CRS)
    dates = []
    for c0 in range(0, n, CHUNK_M // STEP_M):
        mid = line.interpolate((c0 + CHUNK_M // STEP_M / 2) * STEP_M)
        lon, lat = gpd.GeoSeries([mid], crs=CRS).to_crs(4326).iloc[0].coords[0]
        shot = tried(chips.clearest, lon, lat, CROP_HALF_KM, start, end)
        print(epoch, f"km {c0 * STEP_M / 1000:.1f}", shot[0] if shot else "-", flush=True)
        if not shot:
            continue
        dates.append(str(shot[0]))
        rgb = shot[1]
        h, w = rgb.shape[:2]
        x0, y0, x1, y1 = chips._bbox(lon, lat, CROP_HALF_KM)
        for col in range(c0, min(n, c0 + CHUNK_M // STEP_M)):
            d = col * STEP_M
            p, q = line.interpolate(d), line.interpolate(min(d + STEP_M, line.length))
            t = np.array([q.x - p.x, q.y - p.y])
            t = t / (np.linalg.norm(t) or 1)
            normal = np.array([t[1], -t[0]])   # right bank side when looking downstream
            offs = (np.arange(rows) - rows / 2 + 0.5) * STEP_M
            pts = np.array([p.x, p.y]) + offs[:, None] * -normal[None, :]   # left bank at the top
            ll = gpd.GeoSeries(gpd.points_from_xy(pts[:, 0], pts[:, 1]), crs=CRS).to_crs(4326)
            cx = ((ll.x - x0) / (x1 - x0) * w).astype(int).clip(0, w - 1)
            cy = ((y1 - ll.y) / (y1 - y0) * h).astype(int).clip(0, h - 1)
            img[:, col] = rgb[cy.values, cx.values]
    del to_ll
    return img, dates


def markers(line):
    s = gpd.read_file("pipeline/out/cache/places/settlements_ghana.geojson").to_crs(CRS)
    s = s[s.place.isin(["town", "city", "village"]) & (s.distance(line) < 2500)]
    towns = [{"name": r["name"], "km": round(line.project(r.geometry) / 1000, 2), "place": r.place,
              "side_m": round(float(r.geometry.distance(line)))} for _, r in s.iterrows() if r["name"]]
    p = gpd.read_file("pipeline/out/places/latest.geojson").to_crs(CRS)
    idx = json.load(open("pipeline/out/places/index.json", encoding="utf-8"))
    p = p[p.distance(line) < STRIP_HALF_M]
    patches = [{"id": r.id, "km": round(line.project(r.geometry.representative_point()) / 1000, 2), "ha": idx[r.id]["ha"],
                "licence": idx[r.id]["licence"], "likely": bool(idx[r.id].get("likely_galamsey"))} for _, r in p.iterrows()]
    return sorted(towns, key=lambda t: t["km"]), sorted(patches, key=lambda t: t["km"])


if __name__ == "__main__":
    line = course()
    print(f"course {line.length / 1000:.1f} km", flush=True)
    towns, patches = markers(line)
    meta = {"length_km": round(line.length / 1000, 2), "step_m": STEP_M, "half_m": STRIP_HALF_M, "towns": towns,
            "patches": patches, "dates": {}}
    for epoch in EPOCHS:
        img, dates = strip(line, epoch)
        Image.fromarray(img).save(f"{OUT}/pra-{epoch}.png")
        meta["dates"][epoch] = sorted(set(dates))
        json.dump(meta, open(f"{OUT}/pra.json", "w", encoding="utf-8"), indent=1)
    print("towns", len(towns), "patches", len(patches))
