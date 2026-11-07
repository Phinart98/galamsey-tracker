"""s36: the water at each of the five treatment plants, in pictures (spike log section 36).

For each plant: the clearest Sentinel-2 picture of each month in the last 24 months, plus the clearest of the
2016-17 and 2017-18 dry seasons, 3 km across around the plant. One strip per plant in date order, so a reader can
see whether the water at the intake looks brown or clear and how that changes.

Run from the repo root: uv run --project pipeline python spike/plants.py
"""
import datetime as dt
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, "pipeline")
from tracker import chips  # noqa: E402

TODAY = dt.date(2026, 11, 7)
HALF_KM = 1.5
SIDE = 220
OUT = "pipeline/out/checks/plants"
os.makedirs(OUT, exist_ok=True)


def months(n):
    y, m = TODAY.year, TODAY.month
    for _ in range(n):
        start = dt.date(y, m, 1)
        end = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1))
        yield start, min(end, TODAY)
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)


def best(lon, lat, start, end):
    bbox = chips._bbox(lon, lat, HALF_KM)
    for item in chips.search(bbox, start, end, 12)[:6]:
        rgb = chips.scene(item, bbox)
        if rgb is not None:
            return item.datetime.date(), rgb
    return None


plants = json.load(open("pipeline/water_plants.geojson", encoding="utf-8"))["features"]
font = ImageFont.load_default(size=15)
for f in plants:
    p = f["properties"]
    windows = [(dt.date(2016, 11, 1), dt.date(2017, 3, 31)), (dt.date(2017, 11, 1), dt.date(2018, 3, 31))]
    windows += sorted(months(24))
    shots = []
    for start, end in windows:
        s = best(p["plant_lon"], p["plant_lat"], start, end)
        if s:
            shots.append(s)
        print(p["plant"], start, bool(s), flush=True)
    cols = 7
    rows = (len(shots) + cols - 1) // cols
    img = Image.new("RGB", (cols * (SIDE + 8) + 8, rows * (SIDE + 24) + 34), "white")
    d = ImageDraw.Draw(img)
    d.text((8, 8), f"{p['plant']} plant on the {p['river']}, 3 km across, clearest picture of each month", fill="black", font=font)
    for i, (day, rgb) in enumerate(shots):
        x, y = 8 + (i % cols) * (SIDE + 8), 30 + (i // cols) * (SIDE + 24)
        img.paste(Image.fromarray(rgb).resize((SIDE, SIDE)), (x, y + 18))
        d.text((x, y), day.strftime("%d %b %Y"), fill="black", font=font)
    img.save(f"{OUT}/{p['plant'].lower()}.png")
    print(p["plant"], len(shots), "pictures", flush=True)
