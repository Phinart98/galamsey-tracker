"""A fresh, blind test of the "open water at the patch" rule (spike log s27).

The rule was noticed on 108 patches judged earlier, so it must be checked on patches it was not chosen on.
30 random active patches with no licence to mine (none or prospecting only), not in spike/signs_labels.json,
drawn by count (the mark applies to each place). The contact sheets are judged by eye first; the water readings
go to a separate file that is opened only after the verdicts are written down.

Run from the repo root: uv run --project pipeline python spike/signs_holdout.py [seed out_dir earlier_readings...]
Batch 1: seed 31 into signs-holdout. Batch 2: seed 32 into signs-holdout-2, leaving out batch 1's patches.
"""
import datetime as dt
import json
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import geopandas as gpd
from PIL import Image, ImageDraw, ImageFont
from pystac_client.exceptions import APIError

sys.path.insert(0, "pipeline")
sys.path.insert(0, "spike")
from signs_features import clearest as measure_clearest  # noqa: E402
from tracker import chips  # noqa: E402
from tracker.run import CHIP_HALF_KM  # noqa: E402

TODAY = dt.date(2026, 10, 27)
SIDE = 300


def retry(fn, *args):
    for attempt in range(3):  # the connection drops now and then
        try:
            return fn(*args)
        except (APIError, OSError):
            time.sleep(20 * (attempt + 1))
    return None


def main():
    seed, OUT, *earlier = (int(sys.argv[1]), sys.argv[2], *sys.argv[3:]) if len(sys.argv) > 2 else (31, "pipeline/out/checks/signs-holdout")
    os.makedirs(OUT, exist_ok=True)
    used = {lab.get("id") for lab in json.load(open("spike/signs_labels.json", encoding="utf-8"))}
    for path in earlier:
        used |= {r["id"] for r in json.load(open(path, encoding="utf-8"))}
    index = json.load(open("pipeline/out/places/index.json", encoding="utf-8"))
    places = gpd.read_file("pipeline/out/places/latest.geojson")
    polys = dict(zip(places["id"], places.geometry))
    pool = sorted((r for r in index.values() if r.get("active") and r["id"] in polys and r["id"] not in used
                   and r["licence"] in ("no licence", "prospecting only")), key=lambda r: r["id"])
    picks = random.Random(seed).sample(pool, 30)
    print(f"pool {len(pool)} active patches with no licence to mine; checking 30", flush=True)

    def check(k, r):
        first = dt.date.fromisoformat(r["first_seen"])
        shots = [retry(chips.clearest, r["lon"], r["lat"], CHIP_HALF_KM, first - dt.timedelta(days=450), first - dt.timedelta(days=1)),
                 retry(chips.clearest, r["lon"], r["lat"], CHIP_HALF_KM, first, TODAY)]
        cell = (f"{k}. {r['ha']:.1f} ha {r.get('near') or r.get('district')} first {r['first_seen']} "
                + " / ".join(str(s[0]) if s else "-" for s in shots), shots)
        reading = {"n": k, "id": r["id"], "ha": r["ha"], **(retry(measure_clearest, polys[r["id"]], r["first_seen"]) or {})}
        print(f"  {k} done", flush=True)  # no readings on screen: the sheets are judged blind
        return cell, reading

    # Several at once: the time goes on waiting for the network, not on the computer
    with ThreadPoolExecutor(5) as pool_:
        done = list(pool_.map(check, range(1, len(picks) + 1), picks))
    cells, readings = [c for c, _ in done], [r for _, r in done]

    font = ImageFont.load_default(size=16)
    for s in range(0, len(cells), 6):
        part = cells[s:s + 6]
        img = Image.new("RGB", (2 * (2 * SIDE + 10) + 30, ((len(part) + 1) // 2) * (SIDE + 30) + 30), "white")
        d = ImageDraw.Draw(img)
        d.text((10, 6), "Fresh blind check: random patches with no licence to mine. Before / now", fill="black", font=font)
        for i, (label, shots) in enumerate(part):
            x, y = (i % 2) * (2 * SIDE + 25) + 10, 30 + (i // 2) * (SIDE + 30)
            d.text((x, y), label[:72], fill="black", font=font)
            for j, shot in enumerate(shots):
                if shot:
                    img.paste(Image.fromarray(shot[1]).resize((SIDE, SIDE)), (x + j * (SIDE + 5), y + 22))
        img.save(f"{OUT}/sheet-{s // 6 + 1}.png")
    json.dump(readings, open(f"{OUT}/readings-sealed.json", "w"), indent=1)
    print("sheets written; readings sealed", flush=True)


if __name__ == "__main__":
    main()
