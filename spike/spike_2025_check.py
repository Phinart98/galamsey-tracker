"""Was the early-2025 jump in tile 30NYN (Atiwa and Kwahu) mining, or dry-season farm and fire clearing?

Samples patches in the May 2025 trend point first seen 22 Feb to 22 May 2025, and shows each one
before, soon after, and now. Farm and fire clearing usually turns green again within a year; mining pits do not.

Run from the repo root: uv run --project pipeline python spike/spike_2025_check.py T30NYN
"""
import datetime as dt
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont
from pyproj import Transformer

sys.path.insert(0, "pipeline")
from tracker import chips, nasa  # noqa: E402
from tracker.check_tile import sample  # noqa: E402
from tracker.dist import cluster_polygons, reading_days, window_mask  # noqa: E402
from tracker.run import BELT_BBOX, CHIP_HALF_KM  # noqa: E402

TILE = sys.argv[1] if len(sys.argv) > 1 else "T30NYN"
M = dt.date(2025, 5, 22)
SINCE = dt.date(2025, 2, 22)
TODAY = dt.date(2026, 10, 25)
SIDE = 260
OUT = f"pipeline/out/checks/spike-2025-{TILE}"
os.makedirs(OUT, exist_ok=True)

days, _ = reading_days(M, TODAY)
entries = [nasa.latest_per_tile(BELT_BBOX, d)[TILE] for d in days]
readings = [nasa.read_status_and_date(e) for e in entries]
mask, date = window_mask([(r[0], r[1]) for r in readings], M)
g = cluster_polygons(mask, date, readings[0][2], readings[0][3])
g = g[g.first_seen >= str(SINCE)]
print(f"{TILE}: {len(g)} patches first seen {SINCE} to {M}, {g.ha.sum():.0f} ha", flush=True)
to_ll = Transformer.from_crs(g.crs, 4326, always_xy=True)

cells, records = [], []
for k, row in enumerate(sample(g, 20, seed=11), 1):
    pt = row.geometry.representative_point()
    lon, lat = to_ll.transform(pt.x, pt.y)
    first = dt.date.fromisoformat(row.first_seen)
    shots = [chips.clearest(lon, lat, CHIP_HALF_KM, first - dt.timedelta(days=450), first - dt.timedelta(days=1)),
             chips.clearest(lon, lat, CHIP_HALF_KM, first, first + dt.timedelta(days=150)),
             chips.clearest(lon, lat, CHIP_HALF_KM, TODAY - dt.timedelta(days=240), TODAY)]
    label = f"{k}. {row.ha:.1f} ha  {lat:.4f}, {lon:.4f}  first {row.first_seen}  " + " / ".join(str(s[0]) if s else "-" for s in shots)
    cells.append((label, shots))
    records.append({"n": k, "ha": float(row.ha), "lat": round(lat, 5), "lon": round(lon, 5), "first_seen": row.first_seen,
                    "dates": [str(s[0]) if s else None for s in shots]})
    print(" ", label, flush=True)

font = ImageFont.load_default(size=16)
for s in range(0, len(cells), 5):
    part = cells[s:s + 5]
    img = Image.new("RGB", (3 * SIDE + 30, len(part) * (SIDE + 30) + 30), "white")
    d = ImageDraw.Draw(img)
    d.text((10, 6), f"{TILE}: first seen Feb to May 2025. Before / soon after / now", fill="black", font=font)
    for i, (label, shots) in enumerate(part):
        y = 30 + i * (SIDE + 30)
        d.text((10, y), label, fill="black", font=font)
        for j, shot in enumerate(shots):
            if shot:
                img.paste(Image.fromarray(shot[1]).resize((SIDE, SIDE)), (10 + j * (SIDE + 5), y + 22))
    img.save(f"{OUT}/sheet-{s // 5 + 1}.png")
json.dump({"tile": TILE, "window": [str(SINCE), str(M)], "patches": records}, open(f"{OUT}/sample.json", "w"), indent=1)
