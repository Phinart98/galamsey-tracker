"""Measure simple signs of mining for patches already judged by eye, so a plain rule can be tested (spike log s27).

No machine learning: a handful of numbers from one clear Sentinel-2 scene taken after the patch was first seen,
measured inside the patch outline:
  bare      share of pixels with almost no plants (NDVI < 0.3)
  bright    mean bare-soil index ((SWIR + red) - (NIR + blue)) / (sum), high for exposed soil and tailings
  water     share of pixels within 60 m of the patch that are open water (MNDWI > 0): mining ponds
  green_now median NDVI: farms green up again, mining ground stays bare
  elongation long side / short side of the smallest rotated rectangle: roads and pipelines are long and thin
  compact   4 pi area / perimeter^2: pit fields are ragged, farm blocks are neat

Input: the labelled patches in spike/signs_labels.json ({"id" or "lat"/"lon", "first_seen", "label"}).
Output: pipeline/out/checks/signs/features.csv (or the name given). Run from the repo root:
    uv run --project pipeline python spike/signs_features.py
"""
import csv
import datetime as dt
import json
import os
import sys
import time

import geopandas as gpd
import numpy as np
import rasterio
from pystac_client import Client
from pystac_client.exceptions import APIError
from rasterio.errors import RasterioIOError
from rasterio.features import geometry_mask
from rasterio.warp import transform_bounds, transform_geom
from rasterio.windows import from_bounds
from shapely.geometry import Point, mapping

sys.path.insert(0, "pipeline")
from tracker.chips import COLLECTIONS, EARTH_SEARCH, HTTP  # noqa: E402

OUT = "pipeline/out/checks/signs"
WORK_CRS = "EPSG:32630"
BANDS = ("blue", "green", "red", "nir", "swir16")
CLOUDY = (0, 3, 8, 9, 10)  # no data, shadow, cloud, cirrus
TODAY = dt.date(2026, 10, 26)


def read(href, bounds_ll, shape=None):
    with rasterio.Env(**HTTP), rasterio.open(href) as src:
        b = transform_bounds(4326, src.crs, *bounds_ll)
        win = from_bounds(*b, src.transform)
        data = src.read(1, window=win, boundless=True, fill_value=0, out_shape=shape).astype("float32")
        return data, src.window_transform(win) if shape is None else None, src.crs


def measure(item, poly_ll):
    """Feature dict from one scene, or None if the patch is cloudy or the read fails."""
    area = gpd.GeoSeries([poly_ll], crs=4326).to_crs(WORK_CRS)
    ring = area.buffer(60).to_crs(4326).iloc[0]
    bounds = ring.bounds
    try:
        red, transform, crs = read(item.assets["red"].href, bounds)
        shape = red.shape
        scl, _, _ = read(item.assets["scl"].href, bounds, shape)
        inside = ~geometry_mask([transform_geom(4326, crs, mapping(poly_ll))], shape, transform)
        near = ~geometry_mask([transform_geom(4326, crs, mapping(ring))], shape, transform)
        if inside.sum() < 5 or np.isin(scl[near], CLOUDY).mean() > 0.05:
            return None
        b = {"red": red}
        for name in BANDS:
            if name != "red":
                b[name] = read(item.assets[name].href, bounds, shape)[0]
    except (RasterioIOError, KeyError):
        return None
    eps = 1e-6
    ndvi = (b["nir"] - b["red"]) / (b["nir"] + b["red"] + eps)
    bsi = ((b["swir16"] + b["red"]) - (b["nir"] + b["blue"])) / ((b["swir16"] + b["red"]) + (b["nir"] + b["blue"]) + eps)
    mndwi = (b["green"] - b["swir16"]) / (b["green"] + b["swir16"] + eps)
    rect = area.iloc[0].minimum_rotated_rectangle
    sides = sorted({round(Point(rect.exterior.coords[i]).distance(Point(rect.exterior.coords[i + 1])), 1) for i in range(2)})
    poly = area.iloc[0]
    return {
        "scene": str(item.datetime.date()),
        "bare": round(float((ndvi[inside] < 0.3).mean()), 3),
        "bright": round(float(bsi[inside].mean()), 3),
        "water": round(float((mndwi[near] > 0).mean()), 3),
        "green_now": round(float(np.median(ndvi[inside])), 3),
        "elongation": round(sides[-1] / max(sides[0], 1.0), 2),
        "compact": round(4 * np.pi * poly.area / poly.length ** 2, 3),
    }


def clearest(poly_ll, first_seen):
    bbox = list(poly_ll.buffer(0.002).bounds)
    cat = Client.open(EARTH_SEARCH, timeout=60)
    items = [i for c in COLLECTIONS for i in cat.search(collections=[c], bbox=bbox, datetime=f"{first_seen}/{TODAY}",
                                                         query={"eo:cloud_cover": {"lt": 30}}, max_items=30).items()]
    for item in sorted(items, key=lambda i: i.properties.get("eo:cloud_cover", 100))[:12]:
        f = measure(item, poly_ll)
        if f:
            return f
    return None


def main():
    os.makedirs(OUT, exist_ok=True)
    labels = json.load(open("spike/signs_labels.json", encoding="utf-8"))
    # Optional: python spike/signs_features.py <source prefix> <output name>, to run two parts side by side
    prefix, name = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("", "features.csv")
    labels = [lab for lab in labels if lab["source"].startswith(prefix)]
    places = gpd.read_file("pipeline/out/places/latest.geojson")
    by_id = dict(zip(places["id"], places.geometry))
    path = f"{OUT}/{name}"
    done = set()
    if os.path.exists(path):
        done = {r["key"] for r in csv.DictReader(open(path, encoding="utf-8"))}
    fields = ["key", "source", "label", "ha", "id", "scene", "bare", "bright", "water", "green_now", "elongation", "compact"]
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new:
            w.writeheader()
        for lab in labels:
            key = f"{lab['source']}-{lab['n']}"
            if key in done:
                continue
            poly = by_id.get(lab.get("id"))
            if poly is None:  # older samples carry only a point: take the current patch under or next to it
                pt = Point(lab["lon"], lab["lat"])
                hit = places[places.intersects(pt.buffer(0.0015))]
                if hit.empty:
                    print(key, "no current outline", flush=True)
                    continue
                poly = hit.geometry.iloc[hit.geometry.distance(pt).argmin()]
                lab = dict(lab, id=hit["id"].iloc[hit.geometry.distance(pt).argmin()])
            f = None
            for attempt in range(3):  # the connection drops now and then
                try:
                    f = clearest(poly, lab["first_seen"])
                    break
                except (APIError, OSError):
                    time.sleep(20 * (attempt + 1))
            if not f:
                print(key, "no clear scene", flush=True)
                continue
            w.writerow({"key": key, "source": lab["source"], "label": lab["label"], "ha": lab["ha"], "id": lab["id"], **f})
            fh.flush()
            print(key, lab["label"], f, flush=True)


if __name__ == "__main__":
    main()
