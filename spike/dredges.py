"""s31: dredges on rivers as bright points in Sentinel-1 radar (spike log section 31).

Step 1 (default): for each test stretch, every Sentinel-1 RTC pass in the last DAYS days from Planetary Computer,
river mask from JRC surface water occurrence, bright objects on the water, fixed spots dropped.
Writes pipeline/out/checks/dredges/detections.json and a per-stretch summary.
Step 2 (`sheets`): 10 random detections (seed 31) next to the nearest Sentinel-2 picture within 3 days.

Run from the repo root: uv run --project pipeline python spike/dredges.py [sheets]
"""
import datetime as dt
import json
import os
import random
import sys
import time

import geopandas as gpd
import numpy as np
import rasterio
import requests
from rasterio.features import rasterize
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import from_bounds
from scipy import ndimage
from shapely.geometry import LineString

sys.path.insert(0, "pipeline")

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
TOKEN = "https://planetarycomputer.microsoft.com/api/sas/v1/token/{}"
TODAY = dt.date(2026, 11, 7)
DAYS = 90
STRETCHES = {  # lon_min, lat_min, lon_max, lat_max
    # Pilot: the Offin through Dunkwa, the stretch most named in dredging reports. The others wait for a faster link.
    "pra-twifo-praso": (-1.58, 5.55, -1.52, 5.66),
}
LATER = {
    "pra-praso-daboase": (-1.70, 5.12, -1.45, 5.65),
    "ankobra-prestea": (-2.25, 5.30, -2.05, 5.55),
    "birim-kibi": (-0.65, 6.05, -0.45, 6.30),
}
CORRIDOR_M = 150      # how far from a mapped river line
DARK_DB = -16.0       # median VV below this is water
MEDIAN_PASSES = 10
SHRINK_PX = 1         # 10 m off the banks at 10 m (rivers here are 5 to 8 pixels wide)
WINDOW_PX = 61        # about 300 m either way at 10 m
BRIGHT_DB = 10.0
MIN_PX, MAX_PX = 1, 30
FIXED_SHARE = 0.5
OUT = "pipeline/out/checks/dredges"
os.makedirs(OUT, exist_ok=True)
_tokens: dict[str, tuple[float, str]] = {}


def sign(href: str, collection: str) -> str:
    t = _tokens.get(collection)
    if not t or t[0] < time.time() + 300:
        r = requests.get(TOKEN.format(collection), timeout=60).json()
        _tokens[collection] = (time.time() + 3000, r["token"])
    return href + "?" + _tokens[collection][1]


def search(collection, bbox, start=None, end=None):
    body = {"collections": [collection], "bbox": list(bbox), "limit": 200}
    if start:
        body["datetime"] = f"{start}T00:00:00Z/{end}T23:59:59Z"
    r = requests.post(STAC, json=body, timeout=120)
    r.raise_for_status()
    return r.json()["features"]


def read_window(href, bbox, dst=None):
    """Read bbox from a COG. With dst=(shape, transform, crs) the result is resampled onto that grid."""
    with rasterio.Env(GDAL_HTTP_MAX_RETRY="4", GDAL_HTTP_RETRY_DELAY="3"):
        with rasterio.open(href) as s:
            if dst is None:
                b = transform_bounds("EPSG:4326", s.crs, *bbox)
                w = from_bounds(*b, transform=s.transform).round_offsets().round_lengths()
                return s.read(1, window=w, boundless=True, fill_value=0).astype("float32"), s.window_transform(w), s.crs
            shape, transform, crs = dst
            b = transform_bounds("EPSG:4326", s.crs, *bbox)
            w = from_bounds(*b, transform=s.transform).round_offsets().round_lengths()
            src = s.read(1, window=w, boundless=True, fill_value=0).astype("float32")
            out = np.zeros(shape, "float32")
            reproject(src, out, src_transform=s.window_transform(w), src_crs=s.crs, dst_transform=transform, dst_crs=crs,
                      resampling=Resampling.nearest)
            return out


def river_lines(bbox):
    q = (f'[out:json][timeout:120];way["waterway"="river"]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});out geom;')
    for attempt in range(6):
        url = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter")[attempt % 2]
        try:
            r = requests.post(url, data={"data": q}, timeout=180,
                              headers={"User-Agent": "galamsey-tracker research (open data project)"})
            r.raise_for_status()
            break
        except requests.RequestException as e:
            print("  overpass retry", e, flush=True)
            time.sleep(15 * (attempt + 1))
    return [LineString([(p["lon"], p["lat"]) for p in w["geometry"]]) for w in r.json()["elements"] if len(w.get("geometry", [])) > 1]


def river_mask(bbox, grid, median_db):
    """Dark to radar most of the time (water), near a mapped river, shrunk off the banks."""
    lines = gpd.GeoSeries(river_lines(bbox), crs=4326).to_crs(grid[2]).buffer(CORRIDOR_M)
    corridor = rasterize([(g, 1) for g in lines], out_shape=grid[0], transform=grid[1]).astype(bool) if len(lines) else np.zeros(grid[0], bool)
    water = corridor & (median_db < DARK_DB)
    return ndimage.binary_erosion(water, iterations=SHRINK_PX)


def masked_mean(db, mask):
    """Mean of db over mask pixels in a WINDOW_PX square around each pixel."""
    s = ndimage.uniform_filter(np.where(mask, db, 0).astype("float64"), WINDOW_PX)
    n = ndimage.uniform_filter(mask.astype("float64"), WINDOW_PX)
    return np.where(n > 0, s / np.maximum(n, 1e-9), np.nan)


def read_vv(f, bbox, grid):
    vv, transform, crs = read_window(sign(f["assets"]["vv"]["href"], "sentinel-1-rtc"), bbox)
    if grid is not None and (vv.shape, transform, crs) != grid:
        vv = read_window(sign(f["assets"]["vv"]["href"], "sentinel-1-rtc"), bbox, grid)
    return vv, (vv.shape, transform, crs)


def detect(name, bbox):
    items = sorted(search("sentinel-1-rtc", bbox, TODAY - dt.timedelta(days=DAYS), TODAY),
                   key=lambda f: f["properties"]["datetime"])
    # 1. River mask from the median of 10 passes spread over the period
    grid, stack = None, []
    for f in items[:: max(1, len(items) // MEDIAN_PASSES)][:MEDIAN_PASSES]:
        vv, g = read_vv(f, bbox, grid)
        grid = grid or g
        stack.append(np.where(vv > 0, 10 * np.log10(np.maximum(vv, 1e-9)), np.nan).astype("float32"))
    median_db = np.nanmedian(np.stack(stack), axis=0)
    del stack
    mask = river_mask(bbox, grid, median_db)
    print(f"{name}: {len(items)} passes, grid {grid[0]}, river pixels {int(mask.sum())}", flush=True)
    # 2. Bright objects on every pass; keep only what is needed for the fixed-spot test and the detections
    seen = np.zeros(grid[0], np.int16)
    hits = np.zeros(grid[0], np.int16)
    found = []
    for f in items:
        try:
            vv, _ = read_vv(f, bbox, grid)
        except rasterio.errors.RasterioIOError as e:
            print("  skip", f["id"], e, flush=True)
            continue
        valid = mask & (vv > 0)
        if valid.sum() < 0.5 * mask.sum():
            continue
        db = 10 * np.log10(np.where(vv > 0, vv, np.nan))
        bright = valid & (db >= masked_mean(db, valid) + BRIGHT_DB)
        seen += valid
        hits += bright
        labels, _ = ndimage.label(bright, structure=np.ones((3, 3)))
        for k, sl in enumerate(ndimage.find_objects(labels), 1):
            obj = labels[sl] == k
            if MIN_PX <= int(obj.sum()) <= MAX_PX:
                found.append((f["properties"]["datetime"][:10], f["id"], sl, obj, float(np.nanmax(db[sl][obj]))))
    passes = len({x[1] for x in found}) if found else 0
    fixed = ndimage.binary_dilation((hits > FIXED_SHARE * np.maximum(seen, 1)) & (seen > 0), iterations=2)
    dets = []
    for day, pid, sl, obj, peak in found:
        if fixed[sl][obj].any():
            continue
        r, c = ndimage.center_of_mass(obj)
        x, y = grid[1] * (sl[1].start + c + 0.5, sl[0].start + r + 0.5)
        lon, lat = rasterio.warp.transform(grid[2], "EPSG:4326", [x], [y])
        dets.append({"stretch": name, "day": day, "pass": pid, "lon": round(lon[0], 5), "lat": round(lat[0], 5),
                     "px": int(obj.sum()), "peak_db": round(peak, 1)})
    n_pass = int((seen > 0).any()) and len(items)
    summary = {"passes": n_pass, "passes_with_objects": passes, "river_px": int(mask.sum()),
               "fixed_px": int((fixed & mask).sum()), "detections": len(dets)}
    print(f"  {name}: {summary}", flush=True)
    return dets, summary


def run():
    alld, summ = [], {}
    for name, bbox in STRETCHES.items():
        d, s = detect(name, bbox)
        alld += d
        summ[name] = s
        json.dump({"today": str(TODAY), "days": DAYS, "summary": summ, "detections": alld},
                  open(f"{OUT}/detections.json", "w"), indent=1)


def sheets():
    from PIL import Image, ImageDraw, ImageFont

    from tracker import chips

    data = json.load(open(f"{OUT}/detections.json"))
    dets = data["detections"]
    picks = random.Random(31).sample(dets, min(10, len(dets)))
    side, cells = 360, []
    for k, d in enumerate(picks, 1):
        day = dt.date.fromisoformat(d["day"])
        shot = chips.clearest(d["lon"], d["lat"], 0.4, day - dt.timedelta(days=3), day + dt.timedelta(days=3))
        cells.append((f"{k}. radar {d['day']}  optical {shot[0] if shot else '-'}", shot))
        print(" ", k, d["stretch"], bool(shot), flush=True)
    font = ImageFont.load_default(size=16)
    cols = 3
    img = Image.new("RGB", (cols * (side + 15) + 15, ((len(cells) + cols - 1) // cols) * (side + 30) + 30), "white")
    dr = ImageDraw.Draw(img)
    dr.text((10, 6), "s31 radar bright points on rivers. Sentinel-2 within 3 days, 800 m across, ring = detection", fill="black", font=font)
    for j, (label, shot) in enumerate(cells):
        x, y = (j % cols) * (side + 15) + 10, 30 + (j // cols) * (side + 30)
        dr.text((x, y), label, fill="black", font=font)
        if shot:
            img.paste(Image.fromarray(shot[1]).resize((side, side)), (x, y + 22))
            c = (x + side // 2, y + 22 + side // 2)
            dr.ellipse((c[0] - 16, c[1] - 16, c[0] + 16, c[1] + 16), outline="white", width=2)
    img.save(f"{OUT}/sheet.png")
    json.dump(picks, open(f"{OUT}/sample-sealed.json", "w"), indent=1)


if __name__ == "__main__":
    sheets() if sys.argv[1:] == ["sheets"] else run()
