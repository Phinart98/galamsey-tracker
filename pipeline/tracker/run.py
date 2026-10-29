"""Pipeline entry point.

    uv run python -m tracker.run weekly     # patches, licences, names, ids, summary, status
    uv run python -m tracker.run chips      # before/after images for large places that lack them
    uv run python -m tracker.run signs      # open-water reading for places with no licence to mine
    uv run python -m tracker.run trend      # same-date rolling 12-month totals, one point per month

Small JSON the site needs at build time goes to <repo>/data (committed). Larger files go to
pipeline/out (published to R2 by the workflow).
"""
import argparse
import datetime as dt
import json
import math
import os
import time
import traceback
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

import geopandas as gpd
import pandas as pd
from pyproj import Transformer
from pystac_client.exceptions import APIError

from tracker import chips, licences, nasa, places, refresh, signs, summary, water, zone
from tracker.dist import SETTLE_OFFSETS_MONTHS, cluster_polygons, loss_mask, reading_days, window_mask
from tracker.identity import dedupe_tiles, match_ids

METHOD_VERSION = "2026.10.3"  # .3: only clearing inside the forest zone counts (spike log s20)
BELT_BBOX = "-3.3,4.7,-0.3,7.5"   # southern mining belt covered by v1
WORK_CRS = "EPSG:32630"
CHIP_HALF_KM = 0.8
CHIP_RETRY_DAYS = 7
# NASA usually publishes a reading within days, but some take up to three weeks. A reading counts
# from a week after its day, and a late one only shifts that reading to an image a few days older.
READING_LAG_DAYS = 7
# Earth Search refused 3,725 of 4,866 readings in the first GitHub run (2026-10-28), so a refused place waits and tries again
SIGNS_RETRY_WAITS = (20, 40, 80)

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


def _jsonable(v):
    """pandas marks missing values as NaN, which is not valid JSON and breaks the site build."""
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, list | tuple):
        return [_jsonable(x) for x in v]
    return v


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_jsonable(obj), f, ensure_ascii=False, indent=1, default=str, allow_nan=False)
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

    clusters = zone.inside(dedupe_tiles(per_tile), zone.load()).reset_index(drop=True)
    clusters["licence"] = licences.classify(clusters, licence_layer(today))
    settlements = places.settlements(os.path.join(CACHE, "places"))
    district_polys = places.districts(os.path.join(CACHE, "places"))
    near, near_km, district = places.name(clusters, settlements, district_polys)
    clusters["near"], clusters["near_km"], clusters["district"] = near.values, near_km.values, district.values

    seeds_path = os.path.join(OUT, "places", "seeds.geojson")
    previous = gpd.read_file(seeds_path) if os.path.exists(seeds_path) else None
    to_ll = Transformer.from_crs(WORK_CRS, 4326, always_xy=True)
    clusters, new_aliases = match_ids(clusters, previous, to_ll.transform)

    write_places(clusters, previous, new_aliases, to_ll.transform)
    data_date = max(v["data_date"] for v in tile_status.values() if v.get("data_date"))
    s = summary.summarise(clusters.drop(columns=["geometry", "seed"]), top=12)
    towns = places.towns_near(clusters, settlements, district_polys)
    s.update({"data_date": data_date, "window_days": 365, "tiles": sorted(tile_status), "method_version": METHOD_VERSION,
              "towns_near": {"radius_m": places.NEAR_M, "count": len(towns), "with_5ha": int((towns.ha >= 5).sum())},
              "water": water.upstream(clusters, water.load())})
    _write_json(os.path.join(DATA, "towns.json"), {"data_date": data_date, "radius_m": places.NEAR_M,
                                                   "towns": towns.round({"lat": 4, "lon": 4, "ha": 1}).to_dict("records")})
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
        rec["likely_galamsey"] = signs.likely_galamsey(r.licence, (rec.get("signs") or {}).get("water"))
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


def needs_chips(rec: dict, today: dt.date) -> bool:
    """Active places with no pictures yet, none clear enough when last tried a week or more ago,
    or pictures that are out of date because the place kept growing."""
    if not rec["active"]:
        return False
    chips = rec.get("chips")
    if not chips:
        return True
    if chips.get("missing"):
        return (today - dt.date.fromisoformat(chips["checked"])).days >= CHIP_RETRY_DAYS
    return refresh.due(chips, rec, chips["after"]["date"], today)


def make_chips(today: dt.date, limit: int):
    index_path = os.path.join(OUT, "places", "index.json")
    index = _read_json(index_path, {})
    todo = refresh.queue(index.values(), lambda r: needs_chips(r, today), "chips")[:limit]
    print(f"chips: {len(todo)} places to image")
    for rec in todo:
        old = rec.get("chips") if not (rec.get("chips") or {}).get("missing") else None
        first = dt.date.fromisoformat(rec["first_seen"])
        last = dt.date.fromisoformat(rec["last_seen"])
        try:
            # A retake keeps the before picture: only the place now has changed
            before = None if old else chips.clearest(rec["lon"], rec["lat"], CHIP_HALF_KM, first - dt.timedelta(days=450), first - dt.timedelta(days=1))
            after = chips.clearest(rec["lon"], rec["lat"], CHIP_HALF_KM, last, today)
        except (OSError, APIError) as e:  # a dropped connection once ended a run 86 places in (2026-10-25)
            print(f"  {rec['id']}: skipped, {type(e).__name__}; tried again next run")
            continue
        if old and not after:
            old["checked"] = str(today)
            print(f"  {rec['id']}: no clear picture for a retake, keeping the old one")
            continue
        if not old and (not before or not after):
            rec["chips"] = {"missing": True, "checked": str(today)}
            print(f"  {rec['id']}: no clear pair yet")
            continue
        entry = {"before": old["before"]} if old else {}
        for label, (when, rgb) in (("after", after),) if old else (("before", before), ("after", after)):
            files = {}
            for key, blob in chips.encode(rgb).items():
                rel = f"chips/{rec['id']}/{label}-{key}"
                os.makedirs(os.path.dirname(os.path.join(OUT, rel)), exist_ok=True)
                with open(os.path.join(OUT, rel), "wb") as f:
                    f.write(blob)
                files[key] = rel
            entry[label] = {"date": str(when), "files": files}
        rec["chips"] = {**entry, "ha": rec["ha"]}
        print(f"  {rec['id']}: {entry['before']['date']} -> {after[0]}{' (retake)' if old else ''}")
        _write_json(index_path, index)  # save as we go: a long run that dies keeps its finished images
    _write_json(index_path, index)


def make_signs(today: dt.date, limit: int, workers: int = 4):
    """Water readings for places with no licence to mine, largest first, so a backlog clears over a few runs."""
    index_path = os.path.join(OUT, "places", "index.json")
    index = _read_json(index_path, {})
    todo = refresh.queue(index.values(), lambda r: signs.needs_reading(r, today), "signs")[:limit]
    outlines = gpd.read_file(os.path.join(OUT, "places", "latest.geojson"))
    polys = dict(zip(outlines["id"], outlines.geometry, strict=True))
    print(f"signs: {len(todo)} places to measure")

    def measure(rec):
        for wait in (*SIGNS_RETRY_WAITS, None):
            try:
                # A retake reads only recent pictures, or it would find the same clear day as before
                old = rec.get("signs") or {}
                since = str(today - dt.timedelta(days=refresh.DAYS)) if "water" in old else rec["first_seen"]
                return rec, signs.reading(polys[rec["id"]], since, today)
            except (OSError, APIError) as e:
                if wait is None:
                    print(f"  {rec['id']}: skipped, {type(e).__name__}: {str(e)[:120]}; tried again next run")
                    return rec, False
                time.sleep(wait)

    # Each reading spends most of its time waiting on Earth Search, so several run at once
    with ThreadPoolExecutor(workers) as pool:
        for n, (rec, got) in enumerate(pool.map(measure, [r for r in todo if r["id"] in polys]), 1):
            if got is False:
                continue
            if got:
                rec["signs"] = {**got, "ha": rec["ha"]}
            elif "water" in (rec.get("signs") or {}):
                rec["signs"]["checked"] = str(today)  # no clear picture for a retake: keep the old reading
            else:
                rec["signs"] = {"missing": True, "checked": str(today)}
            rec["likely_galamsey"] = signs.likely_galamsey(rec["licence"], rec["signs"].get("water"))
            if n % 20 == 0:
                _write_json(index_path, index)  # save as we go: a long run that dies keeps its readings
    _write_json(index_path, index)


def readings_as_of(window_end: dt.date, today: dt.date) -> tuple[list[dt.date], bool]:
    return reading_days(window_end, today - dt.timedelta(days=READING_LAG_DAYS))


def needs_point(point: dict | None, tiles: list[str], readings: int) -> bool:
    """A month is recomputed when a new reading has arrived for it, or when the tiles switched on change.

    Readings arrive about once a month, so most weekly runs skip the trend entirely.
    """
    return not point or point.get("covered") != sorted(tiles) or point.get("readings", len(SETTLE_OFFSETS_MONTHS) if point.get("settled") else -1) < readings


def drop_stale(points: dict, tiles: list[str]) -> dict:
    """Points summed over a different set of tiles are not comparable, so they go until they can be redone."""
    return {k: p for k, p in points.items() if p.get("covered") == sorted(tiles)}


def trend(today: dt.date, start: str = "2024-01"):
    """Hectares newly cleared in the 365 days to the 22nd of each month, by licence class, summed over tiles.

    A point is provisional until all its later readings exist, and is recomputed as each one arrives.
    """
    path = os.path.join(DATA, "trend.json")
    series = _read_json(path, {"method_version": METHOD_VERSION, "points": {}})
    if series.get("method_version") != METHOD_VERSION:
        series = {"method_version": METHOD_VERSION, "points": {}}
    tiles = sorted(enabled_tiles())
    months = []
    month = dt.date.fromisoformat(start + "-22")
    while (days := readings_as_of(month, today)[0]):
        if needs_point(series["points"].get(month.strftime("%Y-%m")), tiles, len(days)):
            months.append(month)
        month = (month.replace(day=1) + dt.timedelta(days=32)).replace(day=22)
    if not months:
        series["points"] = drop_stale(series["points"], tiles)
        _write_json(path, series)
        return

    # Tile by tile, so one tile's granules stay cached while its months are worked through:
    # months M, M+2 and M+4 share granules with their neighbours, and 6 is the smallest FIFO that reads each once
    per_month: dict[dt.date, list] = {m: [] for m in months}
    used: dict[dt.date, list] = {m: [] for m in months}
    settled: dict[dt.date, bool] = {}
    searches: dict[dt.date, dict] = {}

    def granules(day: dt.date) -> dict:
        if day not in searches:
            searches[day] = nasa.latest_per_tile(BELT_BBOX, day)
        return searches[day]

    for tile in tiles:
        recent: OrderedDict = OrderedDict()
        for m in months:
            days, settled[m] = readings_as_of(m, today)
            entries = [g[tile] for g in map(granules, days) if tile in g]
            if not entries:
                continue
            readings = []
            for e in entries:
                if e["title"] not in recent:
                    recent[e["title"]] = nasa.read_status_and_date(e)
                    if len(recent) > 6:
                        recent.popitem(last=False)
                readings.append(recent[e["title"]])
            mask, date = window_mask([(r[0], r[1]) for r in readings], m)
            g = cluster_polygons(mask, date, readings[0][2], readings[0][3]).to_crs(WORK_CRS)
            g["tile"] = tile
            per_month[m].append(g)
            used[m] += [e["title"] for e in entries]
        print(f"trend: {tile} done for {len(months)} months", flush=True)

    lic = licence_layer(today)
    forest = zone.load()
    for m in months:
        if not per_month[m]:
            continue
        c = zone.inside(dedupe_tiles(per_month[m]), forest).reset_index(drop=True)
        c["licence"] = licences.classify(c, lic)
        s = summary.summarise(c.drop(columns="geometry"), top=0)
        series["points"][m.strftime("%Y-%m")] = {
            "date": str(m), "total_ha": s["total_ha"], "no_licence_to_mine": s["no_licence_to_mine"],
            "covered": tiles, "settled": settled[m], "readings": len(readings_as_of(m, today)[0]),
            "granules": used[m]}
        print(f"trend {m:%Y-%m}: {s['total_ha']} ha{'' if settled[m] else ' (provisional)'}")
    series["points"] = drop_stale(series["points"], tiles)
    _write_json(path, series)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["weekly", "chips", "signs", "trend"])
    p.add_argument("--today", default=str(dt.date.today()))
    p.add_argument("--limit", type=int, default=60)
    p.add_argument("--workers", type=int, default=4)
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
        elif a.command == "signs":
            make_signs(today, a.limit, a.workers)
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
