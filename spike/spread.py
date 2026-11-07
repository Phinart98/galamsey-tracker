"""s38: watch the clearing spread, from NASA's own dates (spike log section 38).

Every DIST-ALERT pixel carries the day it was first seen cleared. Readings every 3 months since the archive began
give each 30 m cell its earliest confirmed day. Cells are drawn as their day passes over one clear picture taken
before the first day, and the clip ends on a clear picture from now. No cloud-free pictures are needed in between.

Writes pipeline/out/checks/spread/<id>/: cells.json (for the web player), before.png, after.png, clip.mp4, clip.gif.
Run from the repo root: uv run --project pipeline python spike/spread.py <place id> [<place id> ...]
"""
import datetime as dt
import json
import os
import subprocess
import sys
import time

import geopandas as gpd
import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

sys.path.insert(0, "pipeline")
from tracker import chips, nasa  # noqa: E402
from tracker.dist import CONFIRMED_HEAVY_LOSS, EPOCH  # noqa: E402

HALF_KM = 1.2
SIZE = 1080
FPS = 30
MAGENTA = (184, 21, 90)
STYLE = os.environ.get("SPREAD_STYLE", "reveal")   # "reveal": the real ground appears; "pink": marked squares
SUFFIX = "" if STYLE == "reveal" else "-pink"
SUB = {"reveal": "Ground NASA's satellites saw cleared, as it looks now", "pink": "Pink: land NASA's satellites saw cleared"}
FONT = os.environ.get("SPREAD_FONT", "DejaVuSans-Bold.ttf")   # any bold TTF; Pillow finds DejaVu on most systems
OUT = "pipeline/out/checks/spread"


def window_read(entry, bbox):
    urls = nasa.layer_urls(entry)
    for a in range(4):
        try:
            with rasterio.Env(**nasa.gdal_env()):
                out = []
                for layer in ("VEG-DIST-STATUS", "VEG-DIST-DATE"):
                    with rasterio.open("/vsicurl/" + urls[layer]) as s:
                        w = from_bounds(*transform_bounds(4326, s.crs, *bbox), s.transform).round_offsets().round_lengths()
                        out.append(s.read(1, window=w, boundless=True, fill_value=255 if layer.endswith("STATUS") else 0))
                        tr, crs = s.window_transform(w), s.crs
            return out[0], out[1].astype(np.int32), tr, crs
        except rasterio.errors.RasterioIOError:
            time.sleep(15 * (a + 1))
    return None


def earliest_days(bbox, start=dt.date(2023, 3, 1), end=dt.date(2026, 11, 1)):
    """Earliest confirmed heavy-loss day (days since EPOCH) per 30 m cell, 0 where never cleared."""
    first, grid, day = None, None, start
    while day <= end:
        found = []
        for a in range(6):
            try:
                found = nasa.search(nasa.DIST_ALERT, ",".join(map(str, bbox)), day - dt.timedelta(days=12), day)
                break
            except Exception:  # noqa: BLE001  NASA's catalogue times out now and then
                time.sleep(20 * (a + 1))
        if found:
            # the tile that holds the patch most fully: the latest granule of each tile, read them all
            best = {}
            for e in found:
                t = nasa.tile_of(e["title"])
                if t not in best or nasa.acquired(e["title"]) > nasa.acquired(best[t]["title"]):
                    best[t] = e
            for e in best.values():
                r = window_read(e, bbox)
                if r is None:
                    continue
                status, date, tr, crs = r
                if grid is None:
                    grid, first = (status.shape, tr, crs), np.zeros(status.shape, np.int32)
                if status.shape != grid[0]:
                    continue
                hit = np.isin(status, CONFIRMED_HEAVY_LOSS) & (date > 0)
                first = np.where(hit & ((first == 0) | (date < first)), date, first)
            print(" ", day, "cells so far", int((first > 0).sum()) if first is not None else 0, flush=True)
        m = day.month - 1 + 3
        day = day.replace(year=day.year + m // 12, month=m % 12 + 1)
    return first, grid


def clear_picture(lon, lat, start, end):
    for a in range(3):
        try:
            return chips.clearest(lon, lat, HALF_KM, start, end)
        except Exception:  # noqa: BLE001
            time.sleep(20 * (a + 1))
    return None


def where(place):
    """The site's rule: "near X" only within 2 km, else "N km from X"."""
    km = place.get("near_km")
    return f"Near {place['near']}" if km is not None and km <= 2 else f"{round(km)} km from {place['near']}"


def frames(first, before, after, place, out, before_day):
    font = ImageFont.truetype(FONT, 40)
    small = ImageFont.truetype(FONT, 30)
    h, w = first.shape
    days = np.unique(first[first > 0])
    d0, d1 = int(days.min()), int(days.max())
    cell = SIZE / w
    base = Image.fromarray(before).resize((SIZE, SIZE), Image.BILINEAR)
    end_img = Image.fromarray(after).resize((SIZE, SIZE), Image.BILINEAR)
    ha = (first > 0).sum() * 0.09
    date = lambda d: (EPOCH + dt.timedelta(days=int(d))).strftime("%-d %b %Y") if os.name != "nt" else (EPOCH + dt.timedelta(days=int(d))).strftime("%#d %b %Y")

    def plate(img, text, sub=None):
        d = ImageDraw.Draw(img)
        y = SIZE - (130 if sub else 86)
        d.rectangle((0, y, SIZE, SIZE), fill=(0, 0, 0))
        d.text((32, y + 18), text, font=font, fill=(255, 255, 255))
        if sub:
            d.text((32, y + 72), sub, font=small, fill=(220, 220, 220))
        return img

    def overlay(upto):
        if STYLE == "reveal":
            # Each 30 m square switches from the picture before to the picture now on the day NASA saw it cleared,
            # so the ground turns bare the way it looks from above
            m = Image.fromarray(((first > 0) & (first <= upto)).astype("uint8") * 255).resize((SIZE, SIZE), Image.NEAREST)
            m = m.filter(ImageFilter.GaussianBlur(SIZE / first.shape[1] * 0.35))   # soften the 30 m square edges a little
            return Image.composite(end_img, base, m)
        img = base.copy()
        layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        ys, xs = np.nonzero((first > 0) & (first <= upto))
        for y, x in zip(ys, xs):
            d.rectangle((x * cell, y * cell, (x + 1) * cell, (y + 1) * cell), fill=MAGENTA + (190,))
        img.paste(layer, (0, 0), layer)
        return img

    n = 0
    def save(img, count):
        nonlocal n
        for _ in range(count):
            img.save(f"{out}/f{n:05d}.png")
            n += 1

    hold = lambda words: max(1000, 400 + 350 * words) / 1000
    intro = f"{where(place)}, {before_day.strftime('%#d %b %Y') if os.name == 'nt' else before_day.strftime('%-d %b %Y')}"
    save(plate(base.copy(), intro, "Before the clearing"), int(FPS * hold(len(intro.split()) + 4)))
    steps = int(FPS * 6)  # 6 s of spreading at even steps of time
    for i in range(steps + 1):
        upto = d0 + (d1 - d0) * i / steps
        save(plate(overlay(upto), date(upto), SUB[STYLE]), 1)
    last = plate(overlay(d1), date(d1), SUB[STYLE])
    save(last, int(FPS * 1.2))
    for i in range(1, 13):  # 400 ms crossfade to the newest picture
        save(Image.blend(last, plate(end_img.copy(), "Now"), i / 12), 1)
    since = "early 2023" if d0 <= (dt.date(2023, 3, 31) - EPOCH).days else date(d0)  # the archive starts in Jan 2023
    outro = f"About {ha:.0f} ha cleared in this picture since {since}"
    save(plate(end_img.copy(), "Now", outro), int(FPS * hold(len(outro.split()) + 1)))
    return n, d0, d1, ha


def run(pid):
    p = gpd.read_file("pipeline/out/places/latest.geojson").set_index("id")
    idx = json.load(open("pipeline/out/places/index.json", encoding="utf-8"))[pid]
    c = p.loc[pid].geometry.representative_point()
    bbox = chips._bbox(c.x, c.y, HALF_KM)
    out = f"{OUT}/{pid}"
    os.makedirs(out, exist_ok=True)
    first, grid = earliest_days(bbox)
    if first is None or not (first > 0).any():
        print(pid, "no cleared cells")
        return
    d0 = EPOCH + dt.timedelta(days=int(first[first > 0].min()))
    before = clear_picture(c.x, c.y, d0 - dt.timedelta(days=500), d0 - dt.timedelta(days=1))
    after = clear_picture(c.x, c.y, dt.date(2025, 11, 1), dt.date(2026, 11, 7))
    print(pid, "before", before and before[0], "after", after and after[0], flush=True)
    Image.fromarray(before[1]).save(f"{out}/before.png")
    Image.fromarray(after[1]).save(f"{out}/after.png")
    json.dump({"id": pid, "near": idx.get("near"), "district": idx.get("district"), "ha_patch": idx["ha"], "licence": idx["licence"],
               "epoch": str(EPOCH), "before": str(before[0]), "after": str(after[0]), "bbox": bbox, "shape": list(first.shape),
               "days": first.tolist()}, open(f"{out}/cells.json", "w"))
    for f in os.listdir(out):
        if f.startswith("f") and f.endswith(".png"):
            os.remove(f"{out}/{f}")
    render(pid, first, before[1], after[1], idx, out, before[0])


def render(pid, first, before, after, idx, out, before_day):
    n, a, b, ha = frames(first, before, after, idx, out, before_day)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", f"{out}/f%05d.png", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-crf", "23", f"{out}/clip{SUFFIX}.mp4"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{out}/clip{SUFFIX}.mp4", "-vf",
                    "fps=12,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse", f"{out}/clip{SUFFIX}.gif"], check=True)
    for f in os.listdir(out):
        if f.startswith("f") and f.endswith(".png"):
            os.remove(f"{out}/{f}")
    print(pid, f"{n} frames, {n / FPS:.1f} s, days {EPOCH + dt.timedelta(days=a)} to {EPOCH + dt.timedelta(days=b)}, {ha:.0f} ha in view", flush=True)


def rerender(pid):
    """Captions only: reuse the saved cells and pictures."""
    out = f"{OUT}/{pid}"
    c = json.load(open(f"{out}/cells.json"))
    idx = json.load(open("pipeline/out/places/index.json", encoding="utf-8"))[pid]
    render(pid, np.array(c["days"], np.int32), np.array(Image.open(f"{out}/before.png")), np.array(Image.open(f"{out}/after.png")),
           idx, out, dt.date.fromisoformat(c["before"]))


if __name__ == "__main__":
    if sys.argv[1] == "rerender":
        for pid in sys.argv[2:]:
            rerender(pid)
    else:
        for pid in sys.argv[1:]:
            run(pid)
