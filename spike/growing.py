"""s39: "still growing", hectares a place gained in a recent window (spike log section 39).

lag: for five reading days T, hectares first seen from T-150 to T-60 counted from the granules on T and on T+120.
eye: today's places with >= 2 ha in today's window, seeded order, before/after crops until 10 have a clear pair.

Run from the repo root: uv run --project pipeline python spike/growing.py lag|eye
"""
import datetime as dt
import json
import os
import random
import sys
import time

import geopandas as gpd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from rasterio.features import rasterize

sys.path.insert(0, "pipeline")
from tracker import chips, nasa, zone  # noqa: E402
from tracker.config import BELT_BBOX  # noqa: E402
from tracker.dist import CONFIRMED_HEAVY_LOSS, EPOCH  # noqa: E402
from tracker.run import enabled_tiles  # noqa: E402

START, END = 150, 60          # window: T-150 to T-60 days
SETTLE = 120                  # settled count read on T+120
DAYS = [dt.date(2025, 7, 1), dt.date(2025, 10, 1), dt.date(2026, 1, 1), dt.date(2026, 4, 1), dt.date(2026, 7, 1)]
OUT = "pipeline/out/checks/growing"
os.makedirs(OUT, exist_ok=True)
TILES = list(enabled_tiles())
ZONE = zone.load()
_zone_cache: dict = {}


def tried(fn, *a, attempts=6):
    for k in range(attempts):
        try:
            return fn(*a)
        except Exception as e:  # noqa: BLE001  slow link and catalogue time-outs
            print("   retry", type(e).__name__, flush=True)
            time.sleep(20 * (k + 1))
    raise RuntimeError(f"gave up on {fn.__name__}")


def granules(day):
    g = tried(nasa.latest_per_tile, BELT_BBOX, day)
    return {t: g[t] for t in TILES if t in g}


def zone_mask(tile, shape, transform, crs):
    if tile not in _zone_cache:
        z = gpd.GeoSeries([ZONE], crs=4326).to_crs(crs).iloc[0]
        _zone_cache[tile] = rasterize([(z, 1)], out_shape=shape, transform=transform).astype(bool)
    return _zone_cache[tile]


def window(date, status, t):
    lo, hi = (t - dt.timedelta(days=START) - EPOCH).days, (t - dt.timedelta(days=END) - EPOCH).days
    return np.isin(status, CONFIRMED_HEAVY_LOSS) & (date >= lo) & (date <= hi)


def lag():
    rows = []
    for t in DAYS:
        early, late = granules(t), granules(t + dt.timedelta(days=SETTLE))
        e_ha = l_ha = 0.0
        for tile in TILES:
            if tile not in early or tile not in late:
                print(" ", t, tile, "missing a granule", flush=True)
                continue
            for entry, key in ((early[tile], "e"), (late[tile], "l")):
                status, date, tr, crs = tried(nasa.read_status_and_date, entry)
                ha = float((window(date, status, t) & zone_mask(tile, status.shape, tr, crs)).sum()) * 0.09
                if key == "e":
                    e_ha += ha
                else:
                    l_ha += ha
            print(" ", t, tile, f"early {e_ha:.0f} settled {l_ha:.0f}", flush=True)
        rows.append({"T": str(t), "window": f"{t - dt.timedelta(days=START)} to {t - dt.timedelta(days=END)}",
                     "early_ha": round(e_ha), "settled_ha": round(l_ha), "ratio": round(e_ha / l_ha, 3) if l_ha else None})
        print(rows[-1], flush=True)
        json.dump(rows, open(f"{OUT}/lag.json", "w"), indent=1)


def eye():
    places = gpd.read_file("pipeline/out/places/latest.geojson")
    today = max(dt.date.fromisoformat(v) for v in [json.load(open("data/summary/latest.json"))["data_date"]])
    w0, w1 = today - dt.timedelta(days=START), today - dt.timedelta(days=END)
    grew = np.zeros(len(places))
    for tile, entry in granules(today).items():
        status, date, tr, crs = tried(nasa.read_status_and_date, entry)
        idx = rasterize([(g, i + 1) for i, g in enumerate(places.to_crs(crs).geometry)], out_shape=status.shape,
                        transform=tr, dtype="int32")
        m = window(date, status, today) & (idx > 0)
        counts = np.bincount(idx[m], minlength=len(places) + 1)[1:] * 0.09
        grew = np.maximum(grew, counts)   # overlapping tiles see the same pixels: keep the larger
        print(" ", tile, f"{counts.sum():.0f} ha in window", flush=True)
    places["grew_ha"] = grew
    cand = places[places.grew_ha >= 2].reset_index(drop=True)
    print(f"{len(cand)} places with >= 2 ha added {w0} to {w1}", flush=True)
    order = list(range(len(cand)))
    random.Random(39).shuffle(order)
    cells, k = [], 0
    for i in order:
        if len(cells) == 10:
            break
        p = cand.iloc[i]
        c = p.geometry.representative_point()
        before = tried(chips.clearest, c.x, c.y, 0.6, w0 - dt.timedelta(days=120), w0)
        after = tried(chips.clearest, c.x, c.y, 0.6, w1, today)
        k += 1
        print(f"  try {k}: {p['id']} {p.grew_ha:.1f} ha, before {before and before[0]}, after {after and after[0]}", flush=True)
        if before and after:
            cells.append((p, before, after))
    side, font = 360, ImageFont.load_default(size=16)
    img = Image.new("RGB", (2 * side + 40, len(cells) * (side + 34) + 34), "white")
    d = ImageDraw.Draw(img)
    d.text((10, 8), f"s39 still growing: window {w0} to {w1}. Left before, right after, ring = place", fill="black", font=font)
    for j, (p, b, a) in enumerate(cells):
        y = 34 + j * (side + 34)
        d.text((10, y), f"{j + 1}. {b[0]} | {a[0]}", fill="black", font=font)
        for x, shot in ((10, b), (side + 30, a)):
            img.paste(Image.fromarray(shot[1]).resize((side, side)), (x, y + 22))
            cx, cy = x + side // 2, y + 22 + side // 2
            d.ellipse((cx - 14, cy - 14, cx + 14, cy + 14), outline="white", width=2)
    img.save(f"{OUT}/eye-sheet.png")
    # sealed: the numbers are opened only after judging
    json.dump([{"n": j + 1, "id": p["id"], "grew_ha": round(p.grew_ha, 1), "ha": p.get("ha")} for j, (p, _, _) in enumerate(cells)],
              open(f"{OUT}/eye-sealed.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    {"lag": lag, "eye": eye}[sys.argv[1]]()
