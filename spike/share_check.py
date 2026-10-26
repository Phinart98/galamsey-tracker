"""What share of the cleared AREA is mining? An area-weighted, season-split random eye check across all live tiles.

Patches are drawn with chance proportional to their hectares, so the share that shows mining estimates the share
of cleared land that is mining (the site's headline is hectares, not patch counts). 20 first seen in the dry season
(November to March) and 20 in the wet season, because dry-season farm and fire clearing behaves differently
(spike log s20). Each patch is shown before (the clearest picture in the 15 months before first seen) and now.

Run from the repo root: uv run --project pipeline python spike/share_check.py
"""
import datetime as dt
import json
import os
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, "pipeline")
from pystac_client.exceptions import APIError  # noqa: E402

from tracker import chips  # noqa: E402
from tracker.run import CHIP_HALF_KM  # noqa: E402

TODAY = dt.date(2026, 10, 26)
PER_SEASON = 20
SIDE = 300
OUT = "pipeline/out/checks/share"
os.makedirs(OUT, exist_ok=True)


def clearest(*args):
    for attempt in range(4):  # the connection drops now and then; one lost request should not end the run
        try:
            return chips.clearest(*args)
        except (APIError, OSError):
            if attempt == 3:
                return None
            time.sleep(20 * (attempt + 1))


def dry(first_seen: str) -> bool:
    return int(first_seen[5:7]) in (11, 12, 1, 2, 3)


index = json.load(open("pipeline/out/places/index.json", encoding="utf-8"))
active = sorted((r for r in index.values() if r.get("active")), key=lambda r: r["id"])
rng = np.random.default_rng(26)
picks = []
for season, pool in (("dry", [r for r in active if dry(r["first_seen"])]), ("wet", [r for r in active if not dry(r["first_seen"])])):
    ha = np.array([r["ha"] for r in pool])
    chosen = rng.choice(len(pool), size=PER_SEASON, replace=False, p=ha / ha.sum())
    picks += [dict(pool[i], season=season) for i in chosen]
    print(f"{season}: {len(pool)} patches, {ha.sum():,.0f} ha; drew {PER_SEASON} by area", flush=True)

cells, records = [], []
for k, r in enumerate(picks, 1):
    first = dt.date.fromisoformat(r["first_seen"])
    shots = [clearest(r["lon"], r["lat"], CHIP_HALF_KM, first - dt.timedelta(days=450), first - dt.timedelta(days=1)),
             clearest(r["lon"], r["lat"], CHIP_HALF_KM, first, TODAY)]
    label = (f"{k}. {r['season']} {r['ha']:.1f} ha {r.get('near') or r.get('district')} first {r['first_seen']} "
             + " / ".join(str(s[0]) if s else "-" for s in shots))
    cells.append((label, shots))
    records.append({"n": k, "id": r["id"], "season": r["season"], "ha": r["ha"], "lat": r["lat"], "lon": r["lon"],
                    "first_seen": r["first_seen"], "tile": r["tile"], "licence": r["licence"]})
    print(" ", label, flush=True)

font = ImageFont.load_default(size=16)
for s in range(0, len(cells), 6):
    part = cells[s:s + 6]
    img = Image.new("RGB", (2 * (2 * SIDE + 10) + 30, ((len(part) + 1) // 2) * (SIDE + 30) + 30), "white")
    d = ImageDraw.Draw(img)
    d.text((10, 6), "Area-weighted random patches. Before / now. The patch is at the centre", fill="black", font=font)
    for i, (label, shots) in enumerate(part):
        x, y = (i % 2) * (2 * SIDE + 25) + 10, 30 + (i // 2) * (SIDE + 30)
        d.text((x, y), label[:72], fill="black", font=font)
        for j, shot in enumerate(shots):
            if shot:
                img.paste(Image.fromarray(shot[1]).resize((SIDE, SIDE)), (x + j * (SIDE + 5), y + 22))
    img.save(f"{OUT}/sheet-{s // 6 + 1}.png")
json.dump({"drawn": str(TODAY), "per_season": PER_SEASON, "patches": records}, open(f"{OUT}/sample.json", "w"), indent=1)
