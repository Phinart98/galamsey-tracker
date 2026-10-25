"""Pipeline entry point.

    uv run python -m tracker.run weekly     # patches, licences, names, ids, summary, status
    uv run python -m tracker.run chips      # before/after images for large places that lack them
    uv run python -m tracker.run trend      # same-date rolling 12-month totals, one point per month

Small JSON the site needs at build time goes to <repo>/data (committed). Larger files go to
pipeline/out (published to R2 by the workflow).
"""
import argparse
import datetime as dt
import json
import os
import traceback
from collections import OrderedDict

import geopandas as gpd
import pandas as pd
from pyproj import Transformer

from tracker import chips, licences, nasa, places, summary
from tracker.dist import cluster_polygons, loss_mask, reading_days, window_mask
from tracker.identity import dedupe_tiles, match_ids

METHOD_VERSION = "2026.10.2"
BELT_BBOX = "-3.3,4.7,-0.3,7.5"   # southern mining belt covered by v1
WORK_CRS = "EPSG:32630"
CHIP_MIN_HA = 3.0
CHIP_HALF_KM = 0.8

PIPELINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(PIPELINE_DIR)
DATA = os.path.join(REPO, "data")
OUT = os.path.join(PIPELINE_DIR, "out")
CACHE = os.path.join(OUT, "cache")


def _read_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)
    os.replace(tmp, path)


def enabled_tiles() -> dict:
    return {t: v for t, v in _read_json(os.path.join(PIPELINE_DIR, "tiles.json"), {}).items() if v.get("enabled")}


def licence_layer(today: dt.date) -> gpd.GeoDataFrame:
    path = os.path.join(CACHE, "licences", f"{today}.geojson")
    if not os.path.exists(path):
        _write_json(path, licences.fetch())
    lic, bad = licences.parse(licences.load(path))
    print(f"licences: {len(lic)} usable, {bad} unrepairable")
    return lic


def weekly(today: dt.date):
    tiles = enabled_tiles()
    granules = nasa.latest_per_tile(BELT_BBOX, today)
    per_tile, tile_status = [], {}
    for tile in tiles:
        entry = granules.get(tile)
        if entry is None:
            tile_status[tile] = {"granule": None, "note": "no granule in the last 12 days"}
            continue
        status, date, transform, crs = nasa.read_status_and_date(entry)
        data_date = nasa.acquired(entry["title"])
        gdf = cluster_polygons(loss_mask(status, date, data_date), date, transform, crs).to_crs(WORK_CRS)
        gdf["tile"] = tile
        per_tile.append(gdf)
        tile_status[tile] = {"granule": entry["title"], "data_date": str(data_date), "patches": len(gdf)}
        print(f"{tile}: {len(gdf)} patches, data up to {data_date}")
    if not per_tile:
        raise RuntimeError("no enabled tile had a recent granule")

    clusters = dedupe_tiles(per_tile)
    clusters["licence"] = licences.classify(clusters, licence_layer(today))
    ll = clusters.to_crs(4326).total_bounds
    near, near_km, district = places.name(
        clusters, places.settlements(os.path.join(CACHE, "places"), tuple(ll + [-0.15, -0.15, 0.15, 0.15])),
        places.districts(os.path.join(CACHE, "places")))
    clusters["near"], clusters["near_km"], clusters["district"] = near.values, near_km.values, district.values

    seeds_path = os.path.join(OUT, "places", "seeds.geojson")
    previous = gpd.read_file(seeds_path) if os.path.exists(seeds_path) else None
    to_ll = Transformer.from_crs(WORK_CRS, 4326, always_xy=True)
    clusters, new_aliases = match_ids(clusters, previous, to_ll.transform)

    write_places(clusters, previous, new_aliases, to_ll.transform)
    data_date = max(v["data_date"] for v in tile_status.values() if v.get("data_date"))
    s = summary.summarise(clusters.drop(columns=["geometry", "seed"]), top=12)
    s.update({"data_date": data_date, "window_days": 365, "tiles": sorted(tile_status), "method_version": METHOD_VERSION})
    _write_json(os.path.join(DATA, "summary", "latest.json"), s)
    _write_json(os.path.join(DATA, "summary", f"{data_date[:7]}.json"), s)
    return tile_status, data_date


def write_places(clusters, previous, new_aliases, to_ll):
    index_path = os.path.join(OUT, "places", "index.json")
    index = _read_json(index_path, {})
    for rec in index.values():
        rec["active"] = False
    for _, r in clusters.iterrows():
        lon, lat = to_ll(r.seed.x, r.seed.y)
        rec = index.setdefault(r.id, {"chips": None})
        rec.update({"id": r.id, "active": True, "ha": round(float(r.ha), 2), "first_seen": r.first_seen,
                    "last_seen": r.last_seen, "licence": r.licence, "near": r.near, "near_km": r.near_km,
                    "district": r.district, "lon": round(lon, 5), "lat": round(lat, 5), "tile": r.tile})
    _write_json(index_path, index)

    aliases_path = os.path.join(DATA, "places", "aliases.json")
    aliases = {**_read_json(aliases_path, {}), **new_aliases}
    _write_json(aliases_path, aliases)

    seeds = gpd.GeoDataFrame({"id": clusters.id, "first_seen": clusters.first_seen},
                             geometry=clusters.seed, crs=clusters.crs)
    if previous is not None:  # keep seeds of places no longer active, so their ids can come back
        seeds = pd.concat([seeds, previous[~previous.id.isin(seeds.id)].to_crs(clusters.crs)], ignore_index=True)
    seeds.to_file(os.path.join(OUT, "places", "seeds.geojson"), driver="GeoJSON")

    shapes = clusters[["id", "ha", "licence", "geometry"]].copy()
    shapes["geometry"] = shapes.geometry.simplify(10)
    shapes.to_crs(4326).to_file(os.path.join(OUT, "places", "latest.geojson"), driver="GeoJSON",
                                COORDINATE_PRECISION=5)


def make_chips(today: dt.date, limit: int):
    index_path = os.path.join(OUT, "places", "index.json")
    index = _read_json(index_path, {})
    todo = sorted((r for r in index.values() if r["active"] and r["ha"] >= CHIP_MIN_HA and not r.get("chips")),
                  key=lambda r: -r["ha"])[:limit]
    print(f"chips: {len(todo)} places to image")
    for rec in todo:
        first = dt.date.fromisoformat(rec["first_seen"])
        last = dt.date.fromisoformat(rec["last_seen"])
        before = chips.clearest(rec["lon"], rec["lat"], CHIP_HALF_KM, first - dt.timedelta(days=450), first - dt.timedelta(days=1))
        after = chips.clearest(rec["lon"], rec["lat"], CHIP_HALF_KM, last, today)
        if not before or not after:
            rec["chips"] = {"missing": True, "checked": str(today)}
            print(f"  {rec['id']}: no clear pair yet")
            continue
        entry = {}
        for label, (when, rgb) in (("before", before), ("after", after)):
            files = {}
            for key, blob in chips.encode(rgb).items():
                rel = f"chips/{rec['id']}/{label}-{key}"
                os.makedirs(os.path.dirname(os.path.join(OUT, rel)), exist_ok=True)
                with open(os.path.join(OUT, rel), "wb") as f:
                    f.write(blob)
                files[key] = rel
            entry[label] = {"date": str(when), "files": files}
        rec["chips"] = entry
        print(f"  {rec['id']}: {before[0]} -> {after[0]}")
        _write_json(index_path, index)  # save as we go: a long run that dies keeps its finished images
    _write_json(index_path, index)


def trend(today: dt.date, start: str = "2024-01"):
    """Hectares newly cleared in the 365 days to the 22nd of each month, by licence class, summed over tiles.

    A point is provisional until all its later readings exist, and is recomputed on every run until then.
    """
    path = os.path.join(DATA, "trend.json")
    series = _read_json(path, {"method_version": METHOD_VERSION, "points": {}})
    if series.get("method_version") != METHOD_VERSION:
        series = {"method_version": METHOD_VERSION, "points": {}}
    lic = licence_layer(today)
    recent: OrderedDict = OrderedDict()  # months M, M+2, M+4 share granules with their neighbours; 6 is the smallest FIFO that reads each once

    def read(entry):
        if entry["title"] not in recent:
            recent[entry["title"]] = nasa.read_status_and_date(entry)
            if len(recent) > 6:
                recent.popitem(last=False)
        return recent[entry["title"]]

    month = dt.date.fromisoformat(start + "-22")
    while month <= today - dt.timedelta(days=3):
        key = month.strftime("%Y-%m")
        if not series["points"].get(key, {}).get("settled"):
            days, settled = reading_days(month, today)
            found = [nasa.latest_per_tile(BELT_BBOX, d) for d in days]
            parts, used = [], []
            for tile in enabled_tiles():
                entries = [g[tile] for g in found if tile in g]
                if not entries or tile not in found[0]:
                    continue
                readings = [read(e) for e in entries]
                mask, date = window_mask([(r[0], r[1]) for r in readings], month)
                transform, crs = readings[0][2], readings[0][3]
                g = cluster_polygons(mask, date, transform, crs).to_crs(WORK_CRS)
                g["tile"] = tile
                parts.append(g)
                used += [e["title"] for e in entries]
            if parts:
                c = dedupe_tiles(parts)
                c["licence"] = licences.classify(c, lic)
                s = summary.summarise(c.drop(columns="geometry"), top=0)
                series["points"][key] = {"date": str(month), "total_ha": s["total_ha"],
                                         "no_licence_to_mine": s["no_licence_to_mine"], "tiles": sorted(set(c.tile)),
                                         "settled": settled, "granules": used}
                print(f"trend {key}: {s['total_ha']} ha{'' if settled else ' (provisional)'}")
                _write_json(path, series)
        month = (month.replace(day=1) + dt.timedelta(days=32)).replace(day=22)
    _write_json(path, series)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["weekly", "chips", "trend"])
    p.add_argument("--today", default=str(dt.date.today()))
    p.add_argument("--limit", type=int, default=60)
    a = p.parse_args()
    today = dt.date.fromisoformat(a.today)
    status_path = os.path.join(DATA, "status.json")
    mine = {**_read_json(status_path, {}).get(a.command, {}),
            "last_attempt": dt.datetime.now(dt.UTC).isoformat(timespec="seconds")}

    def save():  # re-read first, so another command that finished meanwhile keeps its entry
        status = _read_json(status_path, {})
        status[a.command] = mine
        status["method_version"] = METHOD_VERSION
        _write_json(status_path, status)

    try:
        if a.command == "weekly":
            tiles, data_date = weekly(today)
            mine.update({"last_success": mine["last_attempt"], "data_date": data_date, "tiles": tiles, "outcome": "ok"})
        elif a.command == "chips":
            make_chips(today, a.limit)
            mine["outcome"] = "ok"
        else:
            trend(today)
            mine["outcome"] = "ok"
    except Exception as e:  # noqa: BLE001  recorded so the site can say the update is late, then CI fails
        mine["outcome"] = f"failed: {type(e).__name__}: {e}"
        save()
        traceback.print_exc()
        raise SystemExit(1)
    save()

if __name__ == "__main__":
    main()
