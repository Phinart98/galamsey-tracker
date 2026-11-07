"""s30: do NASA's radar alerts (OPERA DIST-ALERT-S1) add mining that the optical alerts (DIST-ALERT-HLS) miss?

Step 1 (default): latest radar granule per enabled tile up to DAY, optical granule nearest the same day, the weekly
run's patch rule on both, then radar-only / shared / optical-only counts. Writes pipeline/out/checks/radar/.
Step 2 (`sheets`): before/after sheets of 20 random radar-only patches (seed 30) for the blind eye check.

Run from the repo root: uv run --project pipeline python spike/radar_alerts.py [sheets]
"""
import datetime as dt
import json
import os
import random
import sys
import time

import geopandas as gpd
import numpy as np
import rasterio

sys.path.insert(0, "pipeline")
from tracker import nasa, zone  # noqa: E402
from tracker.dist import cluster_polygons, decode_date, loss_mask  # noqa: E402
from tracker.identity import dedupe_tiles  # noqa: E402
from tracker.run import BELT_BBOX, WORK_CRS, enabled_tiles  # noqa: E402

RADAR = "OPERA_L3_DIST-ALERT-S1_V1"
DAY = dt.date(2026, 2, 28)
OUT = "pipeline/out/checks/radar"
os.makedirs(OUT, exist_ok=True)


def read(entry, status_layer, date_layer, attempts=3):
    urls = nasa.layer_urls(entry)
    for attempt in range(attempts):
        try:
            with rasterio.Env(**nasa.gdal_env()):
                with rasterio.open("/vsicurl/" + urls[status_layer]) as s:
                    status, transform, crs = s.read(1), s.transform, s.crs
                with rasterio.open("/vsicurl/" + urls[date_layer]) as s:
                    date = s.read(1).astype(np.int32)
            return status, date, transform, crs
        except rasterio.errors.RasterioIOError:
            if attempt == attempts - 1:
                raise
            time.sleep(10 * (attempt + 1))


def latest(short_name, day, lookback):
    best = {}
    for e in nasa.search(short_name, BELT_BBOX, day - dt.timedelta(days=lookback), day):
        t = nasa.tile_of(e["title"])
        if t not in best or nasa.acquired(e["title"]) > nasa.acquired(best[t]["title"]):
            best[t] = e
    return best


def patches(granules, status_layer, date_layer, label):
    per_tile, info = [], {}
    for tile, entry in sorted(granules.items()):
        status, date, transform, crs = read(entry, status_layer, date_layer)
        day = nasa.acquired(entry["title"])
        dated = date[np.isin(status, (6, 8)) & (date >= 0)]
        g = cluster_polygons(loss_mask(status, date, day), date, transform, crs).to_crs(WORK_CRS)
        g["tile"] = tile
        per_tile.append(g)
        info[tile] = {"granule": entry["title"], "day": str(day), "patches": len(g), "ha": round(float(g.ha.sum()), 1),
                      "confirmed_px": int(dated.size),
                      "first_seen_range": [str(decode_date(dated.min())), str(decode_date(dated.max()))] if dated.size else None}
        print(f"{label} {tile} {day}: {len(g)} patches, {g.ha.sum():.0f} ha, first seen {info[tile]['first_seen_range']}", flush=True)
    return zone.inside(dedupe_tiles(per_tile), zone.load()).reset_index(drop=True), info


def compare():
    tiles = list(enabled_tiles())
    radar_g = {t: e for t, e in latest(RADAR, DAY, 40).items() if t in tiles}
    optical_g = {t: e for t, e in nasa.latest_per_tile(BELT_BBOX, DAY, 12).items() if t in tiles}
    print("radar tiles", sorted(radar_g), "optical tiles", sorted(optical_g), flush=True)
    both = sorted(set(radar_g) & set(optical_g))
    radar, rinfo = patches({t: radar_g[t] for t in both}, "GEN-DIST-STATUS", "GEN-DIST-DATE", "radar")
    optical, oinfo = patches({t: optical_g[t] for t in both}, "VEG-DIST-STATUS", "VEG-DIST-DATE", "optical")

    hit_r = gpd.sjoin(radar[["geometry"]], optical[["geometry"]], predicate="intersects", how="left")
    shared_r = hit_r.index[hit_r["index_right"].notna()].unique()
    hit_o = gpd.sjoin(optical[["geometry"]], radar[["geometry"]], predicate="intersects", how="left")
    shared_o = hit_o.index[hit_o["index_right"].notna()].unique()
    radar["shared"] = radar.index.isin(shared_r)
    optical["shared"] = optical.index.isin(shared_o)
    overlap_ha = gpd.overlay(radar[["geometry"]], optical[["geometry"]], how="intersection").area.sum() / 1e4

    stats = {
        "day": str(DAY), "tiles": both,
        "radar": {"patches": len(radar), "ha": round(float(radar.ha.sum()), 1),
                  "only_patches": int((~radar.shared).sum()), "only_ha": round(float(radar.ha[~radar.shared].sum()), 1)},
        "optical": {"patches": len(optical), "ha": round(float(optical.ha.sum()), 1),
                    "only_patches": int((~optical.shared).sum()), "only_ha": round(float(optical.ha[~optical.shared].sum()), 1)},
        "overlap_ha": round(float(overlap_ha), 1),
        "radar_tiles": rinfo, "optical_tiles": oinfo,
    }
    print(json.dumps({k: v for k, v in stats.items() if not k.endswith("_tiles")}, indent=1))
    json.dump(stats, open(f"{OUT}/stats.json", "w"), indent=1)
    radar.to_crs(4326).to_file(f"{OUT}/radar.geojson", driver="GeoJSON")
    optical.to_crs(4326).to_file(f"{OUT}/optical.geojson", driver="GeoJSON")


def tried(fn, *args, attempts=4):
    for a in range(attempts):
        try:
            return fn(*args)
        except Exception as e:  # network drops on a slow link
            print("   retry", type(e).__name__, flush=True)
            time.sleep(20 * (a + 1))
    return None


def sheets():
    from PIL import Image, ImageDraw, ImageFont

    from tracker import chips
    from tracker.run import CHIP_HALF_KM

    radar = gpd.read_file(f"{OUT}/radar.geojson")
    pool = radar[~radar.shared.astype(bool)].reset_index(drop=True)
    picks = random.Random(30).sample(range(len(pool)), min(20, len(pool)))
    print(f"{len(pool)} radar-only patches; checking {len(picks)}", flush=True)
    side, cells, records = 300, [], []
    for k, i in enumerate(picks, 1):
        r = pool.iloc[i]
        pt = r.geometry.representative_point()
        first = dt.date.fromisoformat(str(r["first_seen"])[:10])
        shots = [tried(chips.clearest, pt.x, pt.y, CHIP_HALF_KM, first - dt.timedelta(days=450), first - dt.timedelta(days=1)),
                 tried(chips.clearest, pt.x, pt.y, CHIP_HALF_KM, first, DAY + dt.timedelta(days=120))]
        cells.append((f"{k}. " + " / ".join(str(s[0]) if s else "-" for s in shots), shots))
        records.append({"n": k, "lat": round(pt.y, 5), "lon": round(pt.x, 5), "ha": r["ha"], "first_seen": str(r["first_seen"])[:10]})
        print(" ", k, flush=True)
    font = ImageFont.load_default(size=16)
    for s in range(0, len(cells), 6):
        part = cells[s:s + 6]
        img = Image.new("RGB", (2 * (2 * side + 10) + 30, ((len(part) + 1) // 2) * (side + 30) + 30), "white")
        d = ImageDraw.Draw(img)
        d.text((10, 6), "s30 radar-only patches. Before / after (ring = patch centre)", fill="black", font=font)
        for j, (label, shots) in enumerate(part):
            x, y = (j % 2) * (2 * side + 25) + 10, 30 + (j // 2) * (side + 30)
            d.text((x, y), label[:70], fill="black", font=font)
            for m, shot in enumerate(shots):
                if shot:
                    img.paste(Image.fromarray(shot[1]).resize((side, side)), (x + m * (side + 5), y + 22))
                    c = (x + m * (side + 5) + side // 2, y + 22 + side // 2)
                    d.ellipse((c[0] - 14, c[1] - 14, c[0] + 14, c[1] + 14), outline="white", width=2)
        img.save(f"{OUT}/sheet-{s // 6 + 1}.png")
    json.dump(records, open(f"{OUT}/sample-sealed.json", "w"), indent=1)


if __name__ == "__main__":
    sheets() if sys.argv[1:] == ["sheets"] else compare()
