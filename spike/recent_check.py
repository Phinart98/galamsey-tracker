"""Are small, recent patches inside the forest zone mining or farms? (the mining share for the patches the site
lists first when sorted by newest)

A random 20 active patches under 3 ha, first seen in the last six months, from the last weekly run. Each shown
before (the clearest picture in the 15 months before first seen) and now.

Run from the repo root: uv run --project pipeline python spike/recent_check.py
"""
import datetime as dt
import json
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, "pipeline")
from tracker import chips  # noqa: E402
from tracker.run import CHIP_HALF_KM  # noqa: E402

TODAY = dt.date(2026, 10, 25)
SINCE = str(TODAY - dt.timedelta(days=182))
SIDE = 300
OUT = "pipeline/out/checks/recent-small"
os.makedirs(OUT, exist_ok=True)

index = json.load(open("pipeline/out/places/index.json", encoding="utf-8"))
pool = sorted((r for r in index.values() if r.get("active") and r["ha"] < 3 and r["first_seen"] >= SINCE), key=lambda r: r["id"])
picks = random.Random(13).sample(pool, 20)
print(f"{len(pool)} active patches under 3 ha first seen since {SINCE}; checking 20", flush=True)

cells, records = [], []
for k, r in enumerate(picks, 1):
    first = dt.date.fromisoformat(r["first_seen"])
    shots = [chips.clearest(r["lon"], r["lat"], CHIP_HALF_KM, first - dt.timedelta(days=450), first - dt.timedelta(days=1)),
             chips.clearest(r["lon"], r["lat"], CHIP_HALF_KM, first, TODAY)]
    label = f"{k}. {r['ha']:.1f} ha {r.get('near') or r.get('district')}  first {r['first_seen']}  " + " / ".join(str(s[0]) if s else "-" for s in shots)
    cells.append((label, shots))
    records.append({"n": k, "id": r["id"], "ha": r["ha"], "lat": r["lat"], "lon": r["lon"], "first_seen": r["first_seen"]})
    print(" ", label, flush=True)

font = ImageFont.load_default(size=16)
for s in range(0, len(cells), 6):
    part = cells[s:s + 6]
    img = Image.new("RGB", (2 * (2 * SIDE + 10) + 30, ((len(part) + 1) // 2) * (SIDE + 30) + 30), "white")
    d = ImageDraw.Draw(img)
    d.text((10, 6), "Small patches first seen in the last six months. Before / now", fill="black", font=font)
    for i, (label, shots) in enumerate(part):
        x, y = (i % 2) * (2 * SIDE + 25) + 10, 30 + (i // 2) * (SIDE + 30)
        d.text((x, y), label[:70], fill="black", font=font)
        for j, shot in enumerate(shots):
            if shot:
                img.paste(Image.fromarray(shot[1]).resize((SIDE, SIDE)), (x + j * (SIDE + 5), y + 22))
    img.save(f"{OUT}/sheet-{s // 6 + 1}.png")
json.dump({"since": SINCE, "pool": len(pool), "patches": records}, open(f"{OUT}/sample.json", "w"), indent=1)
