"""Is the 25% fall from May 2025 to May 2026 real? Recompute the trend point tile by tile.

For each tile and each May, the same three readings the trend uses (the 22nd, then two and four months later).
Prints hectares per tile, the share of each reading with no data (a proxy for cloud or gaps), and when in
the 12-month window the cleared land was first seen.

Run from the repo root: uv run --project pipeline python spike/trend_by_tile.py
"""
import datetime as dt
import json
import sys

import numpy as np

sys.path.insert(0, "pipeline")
from tracker import nasa  # noqa: E402
from tracker.dist import cluster_polygons, reading_days, window_mask  # noqa: E402
from tracker.run import BELT_BBOX, enabled_tiles  # noqa: E402

NODATA = 255
MONTHS = [dt.date(2024, 5, 22), dt.date(2025, 5, 22), dt.date(2026, 5, 22)]
today = dt.date(2026, 10, 25)
tiles = sorted(enabled_tiles())
searches = {}
out = {}

for m in MONTHS:
    days, settled = reading_days(m, today)
    for d in days:
        searches.setdefault(d, nasa.latest_per_tile(BELT_BBOX, d))
    for tile in tiles:
        entries = [searches[d][tile] for d in days if tile in searches[d]]
        readings = [nasa.read_status_and_date(e) for e in entries]
        mask, date = window_mask([(r[0], r[1]) for r in readings], m)
        g = cluster_polygons(mask, date, readings[0][2], readings[0][3])
        # When in the window each patch was first seen: quarter 1 is the oldest three months
        first = np.array([dt.date.fromisoformat(str(x)[:10]) for x in g["first_seen"]]) if len(g) else np.array([])
        quarters = [round(float(g.ha[(first > m - dt.timedelta(days=365 - 91 * q)) & (first <= m - dt.timedelta(days=365 - 91 * (q + 1)))].sum()))
                    for q in range(4)] if len(g) else [0, 0, 0, 0]
        out.setdefault(tile, {})[str(m)] = {
            "ha": round(float(g.ha.sum())),
            "no_data": [round(float((r[0] == NODATA).mean()), 3) for r in readings],
            "granules": [e["title"].split("_")[4][:8] for e in entries],
            "ha_by_quarter_first_seen": quarters,
        }
        print(tile, m, out[tile][str(m)], flush=True)

json.dump(out, open("pipeline/out/trend_by_tile.json", "w"), indent=1)
print("\nTile      May 2024  May 2025  May 2026  change 25->26")
for tile in tiles:
    v = [out[tile][str(m)]["ha"] for m in MONTHS]
    print(f"{tile}  {v[0]:8}  {v[1]:8}  {v[2]:8}  {(v[2] / v[1] - 1) * 100:+6.0f}%")
tot = [sum(out[t][str(m)]["ha"] for t in tiles) for m in MONTHS]
print(f"all       {tot[0]:8}  {tot[1]:8}  {tot[2]:8}  {(tot[2] / tot[1] - 1) * 100:+6.0f}%  (tile overlaps counted twice)")
