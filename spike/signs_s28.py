"""Blind batch 3 for "Likely galamsey" (spike log s28): better sheets, and two variants of the water rule.

In batches 1 and 2, five of the six marked patches that were not clear mining were simply unclear in a single
before/now pair. So each sheet now shows four dates: before, soon after first seen, halfway, and the latest clear
picture. Pits that stay open and farms that green up again are easier to tell apart over time.

40 random active patches with no licence to mine, none from the labels or batches 1 and 2 (seed 33). The water
readings go to a sealed file, opened only after the verdicts are written. Up to three clear scenes are measured
per patch, each with open water inside the patch and within 60 m of it, so these rules can be scored:
  R0  current rule: water (MNDWI > 0) within 60 m in the clearest scene
  R1  water within 60 m in at least 2 of the clear scenes (one clear scene: that scene decides)
  R2  water inside the patch itself in the clearest scene

Run from the repo root: uv run --project pipeline python spike/signs_s28.py <batch1 readings> <batch2 readings>
"""
import datetime as dt
import json
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import geopandas as gpd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pystac_client import Client
from pystac_client.exceptions import APIError
from rasterio.errors import RasterioIOError
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom
from shapely.geometry import mapping

sys.path.insert(0, "pipeline")
sys.path.insert(0, "spike")
from signs_features import CLOUDY, WORK_CRS, read  # noqa: E402
from tracker import chips  # noqa: E402
from tracker.chips import COLLECTIONS, EARTH_SEARCH  # noqa: E402
from tracker.run import CHIP_HALF_KM  # noqa: E402

TODAY = dt.date(2026, 10, 29)
OUT = "pipeline/out/checks/signs-holdout-3"
SIDE = 240
N, SEED = 40, 33


def retry(fn, *args):
    for attempt in range(3):  # Earth Search refuses bursts now and then
        try:
            return fn(*args)
        except (APIError, OSError):
            time.sleep(20 * (attempt + 1))
    return None


def water(item, poly_ll):
    """Share of open-water pixels inside the patch and within 60 m of it, or None if cloudy there."""
    ring = gpd.GeoSeries([poly_ll], crs=4326).to_crs(WORK_CRS).buffer(60).to_crs(4326).iloc[0]
    try:
        green, transform, crs = read(item.assets["green"].href, ring.bounds)
        scl = read(item.assets["scl"].href, ring.bounds, green.shape)[0]
        swir = read(item.assets["swir16"].href, ring.bounds, green.shape)[0]
    except (RasterioIOError, KeyError):
        return None
    inside = ~geometry_mask([transform_geom(4326, crs, mapping(poly_ll))], green.shape, transform)
    near = ~geometry_mask([transform_geom(4326, crs, mapping(ring))], green.shape, transform)
    if inside.sum() < 5 or np.isin(scl[near], CLOUDY).mean() > 0.05:
        return None
    wet = (green - swir) / (green + swir + 1e-6) > 0
    return {"scene": str(item.datetime.date()), "inside": round(float(wet[inside].mean()), 3), "near": round(float(wet[near].mean()), 3)}


def scenes(poly_ll, first_seen, want=3, tries=12):
    """Up to `want` clear readings since first seen, clearest first, on different days."""
    cat = Client.open(EARTH_SEARCH, timeout=60)
    bbox = list(poly_ll.buffer(0.002).bounds)
    items = [i for c in COLLECTIONS for i in cat.search(collections=[c], bbox=bbox, datetime=f"{first_seen}/{TODAY}",
                                                         query={"eo:cloud_cover": {"lt": 30}}, max_items=30).items()]
    out, days = [], set()
    for item in sorted(items, key=lambda i: i.properties.get("eo:cloud_cover", 100))[:tries]:
        day = item.datetime.date()
        if day in days:
            continue
        r = water(item, poly_ll)
        if r:
            out.append(r)
            days.add(day)
            if len(out) == want:
                break
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    used = {lab.get("id") for lab in json.load(open("spike/signs_labels.json", encoding="utf-8"))}
    for path in sys.argv[1:]:
        used |= {r["id"] for r in json.load(open(path, encoding="utf-8"))}
    index = json.load(open("pipeline/out/places/index.json", encoding="utf-8"))
    places = gpd.read_file("pipeline/out/places/latest.geojson")
    polys = dict(zip(places["id"], places.geometry))
    pool = sorted((r for r in index.values() if r.get("active") and r["id"] in polys and r["id"] not in used
                   and r["licence"] in ("no licence", "prospecting only")), key=lambda r: r["id"])
    picks = random.Random(SEED).sample(pool, N)
    print(f"pool {len(pool)} active patches with no licence to mine; checking {N}", flush=True)

    def check(k, r):
        first = dt.date.fromisoformat(r["first_seen"])
        mid = first + (TODAY - first) / 2
        windows = [(first - dt.timedelta(days=450), first - dt.timedelta(days=1)),
                   (first, min(first + dt.timedelta(days=90), TODAY)),
                   (mid - dt.timedelta(days=45), mid + dt.timedelta(days=45)),
                   (TODAY - dt.timedelta(days=120), TODAY)]
        shots = [retry(chips.clearest, r["lon"], r["lat"], CHIP_HALF_KM, a, b) for a, b in windows]
        label = f"{k}. {r['ha']:.1f} ha, first seen {r['first_seen']}"
        reading = {"n": k, "id": r["id"], "ha": r["ha"], "scenes": retry(scenes, polys[r["id"]], r["first_seen"]) or []}
        print(f"  {k} done", flush=True)  # no readings on screen: the sheets are judged blind
        return (label, shots), reading

    with ThreadPoolExecutor(4) as ex:
        done = list(ex.map(check, range(1, N + 1), picks))
    cells, readings = [c for c, _ in done], [r for _, r in done]

    font = ImageFont.load_default(size=15)
    per = 5
    for s in range(0, len(cells), per):
        part = cells[s:s + per]
        img = Image.new("RGB", (4 * (SIDE + 5) + 15, len(part) * (SIDE + 44) + 30), "white")
        d = ImageDraw.Draw(img)
        d.text((10, 6), "Blind batch 3: random patches with no licence to mine. Before / first seen / halfway / latest", fill="black", font=font)
        for i, (label, shots) in enumerate(part):
            y = 30 + i * (SIDE + 44)
            d.text((10, y), label, fill="black", font=font)
            for j, shot in enumerate(shots):
                x = 10 + j * (SIDE + 5)
                if shot:
                    img.paste(Image.fromarray(shot[1]).resize((SIDE, SIDE)), (x, y + 20))
                    d.text((x, y + 22 + SIDE), str(shot[0]), fill="black", font=font)
        img.save(f"{OUT}/sheet-{s // per + 1}.png")
    json.dump(readings, open(f"{OUT}/readings-sealed.json", "w"), indent=1)
    print("sheets written; readings sealed", flush=True)


if __name__ == "__main__":
    main()
