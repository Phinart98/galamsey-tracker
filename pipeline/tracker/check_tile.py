"""Contact sheets of random before/after pairs from one tile, for the by-eye check before it is switched on.

    uv run python -m tracker.check_tile T30NXN

Writes pipeline/out/checks/<tile>/sheet-1.png, sheet-2.png and sample.json. The verdicts are recorded
by hand in tiles.json (checked_patches, showed_mining).
"""
import argparse
import datetime as dt
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pyproj import Transformer

from tracker import chips, nasa, zone
from tracker.dist import cluster_polygons, loss_mask
from tracker.run import CHIP_HALF_KM, OUT

GHANA_BBOX = "-3.3,4.5,1.3,11.2"
SIDE = 320
PER_SHEET = 10
BIG_HA = 3.0  # the sample is half from patches this size or more, half from smaller ones


def sample(clusters, n: int, seed: int):
    """Half from patches of at least 3 ha and half from smaller ones, so small clearing is checked too."""
    rng = np.random.default_rng(seed)
    big = clusters[clusters.ha >= BIG_HA]
    small = clusters[clusters.ha < BIG_HA]
    k = min(n // 2, len(big))
    picks = [big.iloc[i] for i in rng.choice(len(big), k, replace=False)]
    picks += [small.iloc[i] for i in rng.choice(len(small), min(n - k, len(small)), replace=False)]
    return picks


def sheet(cells, title: str, path: str):
    font = ImageFont.load_default(size=18)
    cols, rows = 2, (len(cells) + 1) // 2
    w, h = cols * (2 * SIDE + 30), rows * (SIDE + 34) + 40
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    d.text((10, 8), title, fill="black", font=font)
    for k, (label, pair) in enumerate(cells):
        x, y = (k % 2) * (2 * SIDE + 30) + 10, (k // 2) * (SIDE + 34) + 40
        d.text((x, y), label, fill="black", font=font)
        if pair is None:
            d.text((x, y + 40), "no clear pair", fill="gray", font=font)
            continue
        for j, rgb in enumerate(pair):
            img.paste(Image.fromarray(rgb).resize((SIDE, SIDE)), (x + j * (SIDE + 4), y + 24))
    img.save(path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("tile")
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--today", default=str(dt.date.today()))
    a = p.parse_args()
    today = dt.date.fromisoformat(a.today)
    out = os.path.join(OUT, "checks", a.tile)
    os.makedirs(out, exist_ok=True)

    entry = nasa.latest_per_tile(GHANA_BBOX, today)[a.tile]
    status, date, transform, crs = nasa.read_status_and_date(entry)
    clusters = cluster_polygons(loss_mask(status, date, nasa.acquired(entry["title"])), date, transform, crs)
    # Check the same patches the site counts
    clusters = zone.inside(clusters, zone.load())
    to_ll = Transformer.from_crs(crs, 4326, always_xy=True)
    print(f"{a.tile}: {len(clusters)} patches, {round(float(clusters.ha.sum()))} ha")

    cells, records = [], []
    for k, row in enumerate(sample(clusters, a.n, a.seed), 1):
        pt = row.geometry.representative_point()
        lon, lat = to_ll.transform(pt.x, pt.y)
        first, last = dt.date.fromisoformat(row.first_seen), dt.date.fromisoformat(row.last_seen)
        before = chips.clearest(lon, lat, CHIP_HALF_KM, first - dt.timedelta(days=450), first - dt.timedelta(days=1))
        after = chips.clearest(lon, lat, CHIP_HALF_KM, last, today)
        pair = (before[1], after[1]) if before and after else None
        label = f"{k}. {row.ha:.1f} ha  {lat:.4f}, {lon:.4f}" + (f"  {before[0]} / {after[0]}" if pair else "")
        cells.append((label, pair))
        records.append({"n": k, "ha": float(row.ha), "lat": round(lat, 5), "lon": round(lon, 5),
                        "first_seen": row.first_seen, "pair": bool(pair)})
        print(f"  {label}", flush=True)

    for s in range(0, len(cells), PER_SHEET):
        sheet(cells[s:s + PER_SHEET], f"{a.tile} random check, seed {a.seed}",
              os.path.join(out, f"sheet-{s // PER_SHEET + 1}.png"))
    with open(os.path.join(out, "sample.json"), "w", encoding="utf-8") as f:
        json.dump({"tile": a.tile, "seed": a.seed, "granule": entry["title"], "patches": records}, f, indent=1)


if __name__ == "__main__":
    main()
