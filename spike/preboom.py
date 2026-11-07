"""s37: the Pra before the galamsey boom, Landsat 1986-2003 next to Sentinel-2 now (spike log section 37).

Run from the repo root: uv run --project pipeline python spike/preboom.py
"""
import datetime as dt
import json
import os
import sys
import time

import numpy as np
import rasterio
import requests
from PIL import Image, ImageDraw, ImageFont
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

sys.path.insert(0, "pipeline")
sys.path.insert(0, "spike")
from tracker import chips  # noqa: E402
import river_strip  # noqa: E402

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
HALF_KM = 1.5
SIDE = 300
KMS = (0, 20, 35, 50, 67)
OUT = "pipeline/out/checks/preboom"
os.makedirs(OUT, exist_ok=True)
_tok = {}


def sign(href):
    if not _tok or _tok["exp"] < time.time():
        _tok.update(t=requests.get("https://planetarycomputer.microsoft.com/api/sas/v1/token/landsat-c2-l2", timeout=60).json()["token"], exp=time.time() + 2400)
    return href + "?" + _tok["t"]


def search(bbox, start, end, platforms):
    for a in range(5):
        try:
            r = requests.post(STAC, json={"collections": ["landsat-c2-l2"], "bbox": bbox, "datetime": f"{start}/{end}", "limit": 100,
                                          "query": {"eo:cloud_cover": {"lt": 40}, "platform": {"in": platforms}}}, timeout=120)
            r.raise_for_status()
            return sorted(r.json()["features"], key=lambda f: f["properties"]["eo:cloud_cover"])
        except requests.RequestException:
            time.sleep(20 * (a + 1))
    return []


def crop(f, bbox):
    bands = []
    for b in ("red", "green", "blue", "qa_pixel"):
        with rasterio.Env(GDAL_HTTP_MAX_RETRY="4", GDAL_HTTP_RETRY_DELAY="3"), rasterio.open(sign(f["assets"][b]["href"])) as s:
            w = from_bounds(*transform_bounds(4326, s.crs, *bbox), s.transform)
            bands.append(s.read(1, window=w, boundless=True, fill_value=0))
    qa = bands[3].astype("uint16")
    v = np.stack(bands[:3], -1).astype("float32")
    valid = (v.min(-1) > 0) & (qa != 1)
    cloudy = ((qa >> 3) & 1) | ((qa >> 4) & 1) | ((qa >> 1) & 1)   # cloud, cloud shadow, dilated cloud
    cloud = float(cloudy[valid].mean()) if valid.any() else 1.0
    refl = v * 0.0000275 - 0.2
    lo, hi = np.percentile(refl[valid], 2, axis=0), np.percentile(refl[valid], 98, axis=0)
    rgb = np.clip((refl - lo) / np.maximum(hi - lo, 1e-6), 0, 1) ** (1 / 1.3)
    rgb[~valid] = 1
    return (rgb * 255).astype("uint8"), float(valid.mean()), cloud


def months_ok(f):
    return dt.date.fromisoformat(f["properties"]["datetime"][:10]).month in (11, 12, 1, 2, 3)


line = river_strip.course()
import geopandas as gpd  # noqa: E402
pts = gpd.GeoSeries([line.interpolate(k * 1000) for k in KMS], crs=river_strip.CRS).to_crs(4326)
rows, record = [], []
for k, p in zip(KMS, pts):
    bbox = chips._bbox(p.x, p.y, HALF_KM)
    cells = []
    tried_ = []
    for platforms, start, end in ((["landsat-5"], "1984-01-01", "2011-11-30"), (["landsat-7"], "1999-07-01", "2003-05-30")):
        for f in search(bbox, start, end, platforms)[:25]:
            try:
                rgb, ok, cloud = crop(f, bbox)
            except (rasterio.errors.RasterioIOError, IndexError, ValueError):
                continue
            if ok >= 0.98:
                tried_.append((cloud, f["properties"]["datetime"][:10] + " " + f["properties"]["platform"].replace("landsat-", "L"), rgb))
    for cloud, label, rgb in sorted(tried_, key=lambda x: x[0])[:2]:
        cells.append((f"{label} ({cloud:.0%} cloud)", rgb))
    now = chips.clearest(p.x, p.y, HALF_KM, dt.date(2025, 11, 1), dt.date(2026, 3, 15)) or chips.clearest(p.x, p.y, HALF_KM, dt.date(2024, 11, 1), dt.date(2025, 3, 31))
    if now:
        cells.append((str(now[0]) + " (Sentinel-2)", now[1]))
    rows.append((k, cells))
    record.append({"km": k, "lat": round(p.y, 5), "lon": round(p.x, 5), "dates": [c[0] for c in cells]})
    print(k, [c[0] for c in cells], flush=True)

font = ImageFont.load_default(size=15)
cols = max(len(c) for _, c in rows)
img = Image.new("RGB", (cols * (SIDE + 8) + 90, len(rows) * (SIDE + 26) + 30), "white")
d = ImageDraw.Draw(img)
d.text((8, 6), "The Pra before the boom (Landsat, 30 m) and now (Sentinel-2, 10 m). 3 km across.", fill="black", font=font)
for r, (k, cells) in enumerate(rows):
    y = 30 + r * (SIDE + 26)
    d.text((8, y + SIDE // 2), f"km {k}", fill="black", font=font)
    for c, (label, rgb) in enumerate(cells):
        x = 90 + c * (SIDE + 8)
        d.text((x, y), label, fill="black", font=font)
        img.paste(Image.fromarray(rgb).resize((SIDE, SIDE), Image.NEAREST if "Sentinel" not in label else Image.BILINEAR), (x, y + 18))
img.save(f"{OUT}/sheet.png")
json.dump(record, open(f"{OUT}/record.json", "w"), indent=1)
