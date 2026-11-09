"""River walks: six rivers from where they become rivers to the sea (or the river they join), as satellites saw them.

Two steps:
- course (now and then, by hand, needs HydroRIVERS and the OpenStreetMap Ghana extract in pipeline/out/cache):
  the river's line, walked up the main stem from a point near its lower end and pulled onto OpenStreetMap's line,
  saved as pipeline/rivers/<slug>.geojson with the rivers that join it. Rivers do not move, so this is rare.
- pictures (every three months, rivers.yml): 2 km of the newest clear Sentinel-2 picture along that line, read top
  (source) to bottom (sea) with the right bank on the left for a river flowing south, cut into 5 km WebP tiles in
  pipeline/out/rivers/<slug>/<version>/, with pipeline/out/rivers/<slug>.json for the site (towns, joins, plants,
  dates). Both are kept together on the `rivers-state` release, so the data always names tiles that exist.

The weekly run adds `rivers` (km and bank) to every place within 1 km of a walked river: river_places().
"""
import datetime as dt
import glob
import json
import math
import os
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor

import geopandas as gpd
import numpy as np
from PIL import Image
from pyproj import Transformer
from pystac_client.exceptions import APIError
from shapely.geometry import LineString, Point, shape
from shapely.ops import linemerge, nearest_points, substring

from tracker import chips, places, water, zone
from tracker.config import CACHE, OUT, PIPELINE_DIR, WORK_CRS
from tracker.jsonio import write_json

STEP_M = 10            # one picture row (and column) per 10 m: Sentinel-2's pixel
HALF_M = 1000          # 1 km either side of the river
CHUNK_M = 2500         # one satellite crop per 2.5 km of picture
CROP_HALF_KM = 2.3     # a crop 4.6 km across holds the band around its chunk even where the river bends
MIDDLE_M = 1700        # the part of a crop the band can use: clouds outside it do not matter
BLEND_M = 500          # where two crops meet, blended over 500 m
TILE_KM = 5
GUIDE_K = 81           # 2 km box smoothing (81 points 25 m apart), applied twice
CLEAR = 0.97           # a day is clear when this share of a crop's middle has no cloud
SAME_PASS_DAYS = 60    # the piece above's day is kept if it is at most this much older than the newest clear day
TRIES = 8              # satellite days read per crop at most
NEAR_M = 1000          # places within 1 km of the water are marked on the walk
LOOKBACK_DAYS = 365
CONFIG = os.path.join(PIPELINE_DIR, "rivers.json")
COURSES = os.path.join(PIPELINE_DIR, "rivers")
RETRY_WAITS = (20, 40, 60)   # seconds: Earth Search refuses bursts, and a slow link drops downloads
TO_LL = Transformer.from_crs(WORK_CRS, 4326, always_xy=True)
TO_M = Transformer.from_crs(4326, WORK_CRS, always_xy=True)
HYDRO = os.path.join(CACHE, "hydro", "rivers", "HydroRIVERS_v10_af_shp.zip")
OSM = os.path.join(CACHE, "osm", "ghana.osm.pbf")


def config() -> dict:
    with open(CONFIG, encoding="utf-8") as f:
        return {r["slug"]: r for r in json.load(f)}


# ---------------------------------------------------------------------------------------------- geometry


def _points(line: LineString, step: float = 25.0) -> np.ndarray:
    return np.array([line.interpolate(d).coords[0] for d in np.arange(0, line.length, step)] + [line.coords[-1]])


def _box(xy: np.ndarray, k: int, **pad) -> np.ndarray:
    """Moving average over k points along a line of (x, y), padded at both ends as np.pad's `pad` says."""
    return np.stack([np.convolve(np.pad(xy[:, i], k // 2, **pad), np.ones(k) / k, mode="valid") for i in (0, 1)], axis=1)


def guide(line: LineString) -> LineString:
    """The line the picture is cut along: the course smoothed over about 2 km.

    Cut square to the exact course, cross-lines fold over each other inside every bend tighter than the band
    (about 3 in 10 rows on the Pra), which smears and repeats ground. Cut along this smoother line they almost
    never fold, and the river winds inside the band (at most about 500 m off the middle), as it looks from above.
    Point i is the average of course points around i, so it stands for 25 m x i of river. The line is extended
    straight past both ends before smoothing (odd reflection): padding with copies of the end point instead pulled
    each end about 400 m in, so the walk lost the river's last stretch before the sea."""
    once = _box(_points(line), GUIDE_K, mode="reflect", reflect_type="odd")
    return LineString(_box(once, GUIDE_K, mode="reflect", reflect_type="odd"))


def km_left(river: LineString, g: LineString) -> list[float]:
    """River km still to go at every 0.5 km down the picture, then 0. The picture is shorter than the river,
    because bends are not pulled out, so the page counts real river km from this table. Guide point i stands for
    25 m x i of river (see guide)."""
    gxy = np.array(g.coords)
    along = np.minimum(np.arange(len(gxy)) * 25.0, river.length)
    cum = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(gxy, axis=0), axis=1))])
    left = river.length - np.interp(np.arange(0, g.length, 500), cum, along)
    return [round(float(v) / 1000, 2) for v in left] + [0.0]


def _frame(line: LineString, d: float) -> tuple[np.ndarray, np.ndarray]:
    """The point d metres along the line and the unit vector to its right bank (looking downstream), from the
    direction over the next 10 m (the last 10 m at the end)."""
    a, b = (d, d + STEP_M) if d + STEP_M <= line.length else (d - STEP_M, d)
    p, q = line.interpolate(a), line.interpolate(b)
    t = np.array([q.x - p.x, q.y - p.y])
    t /= np.linalg.norm(t) or 1
    c = line.interpolate(d)
    return np.array([c.x, c.y]), np.array([t[1], -t[0]])


def offset(line: LineString, pt: Point) -> float:
    """Metres across the river, positive to the right bank looking downstream: the left of the picture."""
    c, right = _frame(line, line.project(pt))
    return round(float(np.dot([pt.x - c[0], pt.y - c[1]], right)))


def band_points(line: LineString, d: float) -> np.ndarray:
    """The ground points of one picture row, right bank first, every 10 m across 2 km."""
    c, right = _frame(line, d)
    offs = HALF_M - (np.arange(2 * HALF_M // STEP_M) + 0.5) * STEP_M
    return c + offs[:, None] * right[None, :]


def jumps(line: LineString) -> int:
    """Places where the line turns more than 60 degrees within 50 m: what reads as a cut in the picture."""
    xy = _points(line)
    h = np.arctan2(np.diff(xy[:, 1]), np.diff(xy[:, 0]))
    turn = np.abs((h[2:] - h[:-2] + np.pi) % (2 * np.pi) - np.pi)
    return int((np.diff(np.r_[0, (turn > np.radians(60)).astype(int)]) == 1).sum())


def tile_rows(n: int) -> list[tuple[int, int]]:
    """The picture's n rows cut into 5 km tiles, as (first row, row after the last)."""
    rows = TILE_KM * 1000 // STEP_M
    return [(r, min(r + rows, n)) for r in range(0, n, rows)]


def zone_end_km(inside: list[bool], step_km: float = 0.5) -> float | None:
    """Where the river leaves the forest zone for good, from inside/outside every step_km down the picture.
    Clearing is not counted below it, so the page draws a line there."""
    if not inside or inside[-1] or not any(inside):
        return None
    return (max(i for i, v in enumerate(inside) if v) + 1) * step_km


# ---------------------------------------------------------------------------------------------- course


def main_stem(reaches, start, named: set) -> list:
    """HydroRIVERS reach ids from `start` (lowest) up to the source. At each fork the branch on OpenStreetMap's line
    with the river's name (`named`), else the one draining most; a bigger tributary cannot steal the walk. The walk
    stops where no named branch is left and the stream drains under 30 km2."""
    ups = reaches.groupby("NEXT_DOWN").groups
    chain, rid = [], start
    while True:
        chain.append(rid)
        kids = list(ups.get(rid, []))
        if not kids:
            return chain
        on = [k for k in kids if k in named]
        rid = max(on or kids, key=lambda k: reaches.loc[k].UPLAND_SKM)
        if not on and reaches.loc[rid].UPLAND_SKM < 30:
            return chain


def make_course(slug: str) -> dict:
    """Builds and saves the river's course and the rivers joining it. Needs HydroRIVERS (Africa, from
    data.hydrosheds.org) at HYDRO and Geofabrik's Ghana extract at OSM."""
    from scipy.ndimage import median_filter
    every = config()
    cfg = every[slug]
    r = gpd.read_file(f"zip://{HYDRO}!HydroRIVERS_v10_af_shp/HydroRIVERS_v10_af.shp",
                      bbox=(-3.6, 4.4, 0.6, 8.2)).to_crs(WORK_CRS).set_index("HYRIV_ID")
    # every river and stream line in OpenStreetMap's Ghana extract, read once (it is the slow part)
    lines = gpd.read_file(OSM, layer="lines", where="waterway IN ('river', 'stream')").to_crs(WORK_CRS)
    rivers_osm = lines[lines.waterway == "river"]
    names = "|".join([cfg["name"], *cfg.get("aliases", [])])
    osm = lines[lines["name"].fillna("").str.strip().str.match(re.compile(rf"^(river\s+)?({names})(\s+river)?$", re.IGNORECASE))].union_all()
    seed = Point(TO_M.transform(*cfg["seed"]))
    start = r[r.UPLAND_SKM > 300].distance(seed).idxmin()
    # down to the sea, or to where it joins a much larger river
    while r.loc[start].NEXT_DOWN in r.index and r.loc[r.loc[start].NEXT_DOWN].UPLAND_SKM < 1.6 * r.loc[start].UPLAND_SKM:
        start = r.loc[start].NEXT_DOWN
    guiding = osm is not None and not osm.is_empty and osm.length > 0.5 * r.loc[start].DIST_UP_KM * 1000
    named = set(r.index[r.distance(osm) < 500]) if guiding else set()
    chain = main_stem(r, start, named)
    parts = [r.loc[k].geometry for k in reversed(chain)]   # source first
    merged = linemerge(parts)
    line = LineString([c for g in getattr(merged, "geoms", [merged]) for c in g.coords])
    # pulled onto OSM where it is within 1 km: the named line plus unnamed river ways along it (OSM often leaves
    # stretches unnamed). HydroRIVERS follows a 500 m grid and wanders off the channel.
    ways = rivers_osm[rivers_osm["name"].isna()]
    targets = ([osm] if guiding else []) + list(ways[ways.distance(line) < 1000].geometry)
    snap_to = gpd.GeoSeries(targets, crs=WORK_CRS).union_all() if targets else None
    pts = [line.interpolate(d) for d in np.arange(0, line.length, 25)]
    snapped = [nearest_points(snap_to, p)[0] if snap_to is not None else p for p in pts]
    on = np.array([p.distance(q) < 1000 for p, q in zip(pts, snapped)], float)
    raw = np.array([(p.x, p.y) for p in pts])
    shift = np.array([(q.x - p.x, q.y - p.y) if o else (0.0, 0.0) for p, q, o in zip(pts, snapped, on)])
    # a snap that hops onto a side channel or the other arm of a bend for a short way is a jump in the shift: a
    # running median over 2 km drops it (sharp sideways turns on the Pra: 75 without, 6 with)
    shift = np.stack([median_filter(shift[:, i], size=81, mode="nearest") for i in (0, 1)], axis=1)

    w = np.convolve(on, np.ones(21) / 21, mode="same")[:, None]   # snapped stretches keep their meanders
    xy = raw + shift
    course = LineString(w * _box(xy, 5, mode="edge") + (1 - w) * _box(xy, 21, mode="edge"))
    # where the river becomes visible: above the highest reach draining visible_km2 it is under one 10 m pixel wide
    big = [k for k in chain if r.loc[k].UPLAND_SKM >= cfg.get("visible_km2", 500)]
    cut = course.project(Point(r.loc[big[-1]].geometry.coords[0])) if big else 0.0
    course = substring(course, cut, course.length)
    joins = _joins(slug, r, chain, every, rivers_osm[rivers_osm["name"].notna()])
    xy = np.array(course.simplify(2).coords)
    out = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {
        "slug": slug, "streams_km": round(cut / 1000), "joins": joins},
        "geometry": {"type": "LineString", "coordinates": [[round(x, 6), round(y, 6)] for x, y in zip(*TO_LL.transform(xy[:, 0], xy[:, 1]))]}}]}
    write_json(os.path.join(COURSES, f"{slug}.geojson"), out)
    print(f"{slug}: {course.length / 1000:.1f} km of river, {cut / 1000:.0f} km of streams above, "
          f"{jumps(course)} sharp turns, {len(joins)} rivers joining")
    return out


def _joins(slug, r, chain, every, named) -> list[dict]:
    """Branches draining at least 400 km2 that join the walked reaches: where they join, a point 1.5 km up them
    (which bank they come in from) and their name, from our own list or from OpenStreetMap (`named`: named river
    lines). A name loses its trailing " River", so the page can say "The Anum joins here"."""
    seeds = {k: Point(TO_M.transform(*v["seed"])) for k, v in every.items() if k != slug}
    me = "|".join([every[slug]["name"], *every[slug].get("aliases", [])])
    on, out = set(chain), []

    def to_ll(p):
        return [round(c, 5) for c in TO_LL.transform(p.x, p.y)]

    for k in r.index[r.NEXT_DOWN.isin(on) & ~r.index.isin(on) & (r.UPLAND_SKM >= 400)]:
        trunk, rid = [k], k
        for _ in range(40):   # a little way up the branch, to name it
            kids = r.index[r.NEXT_DOWN == rid]
            if not len(kids):
                break
            rid = r.loc[kids].UPLAND_SKM.idxmax()
            trunk.append(rid)
        geom = linemerge([r.loc[i].geometry for i in trunk])
        walked = next((s for s, p in seeds.items() if p.distance(geom) < 3000), None)
        name = every[walked]["name"] if walked else None
        if not name:
            near = named[(named.distance(r.loc[k].geometry) < 1500) & ~named["name"].str.contains(me, case=False)]
            name = near["name"].mode().iloc[0] if len(near) else None
        end = Point(r.loc[k].geometry.coords[-1])
        up = geom.interpolate(max(geom.length * 0.5, geom.length - 1500)) if geom.geom_type == "LineString" else end
        out.append({"name": re.sub(r" River$", "", name) if name else None, "slug": walked, "at": to_ll(end), "up": to_ll(up)})
    return out


def load_course(slug: str, path: str | None = None) -> tuple[LineString, dict]:
    """The saved course in metres (WORK_CRS) and its properties (from `path` if given)."""
    with open(path or os.path.join(COURSES, f"{slug}.geojson"), encoding="utf-8") as f:
        feat = json.load(f)["features"][0]
    xy = np.array(shape(feat["geometry"]).coords)
    return LineString(np.c_[TO_M.transform(xy[:, 0], xy[:, 1])]), feat["properties"]


def _published_course(slug: str) -> str | None:
    """The course the river's published pictures were cut along (saved beside its tiles), if there is one."""
    try:
        with open(os.path.join(OUT, "rivers", f"{slug}.json"), encoding="utf-8") as f:
            version = json.load(f)["version"]
    except (OSError, ValueError, KeyError):
        return None
    path = os.path.join(OUT, "rivers", slug, version, "course.json")
    return path if os.path.exists(path) else None


def lines() -> dict:
    """{slug: (course, guide)} for every river with a saved course. A river with published pictures uses the course
    they were cut along, so its places keep matching the picture after the course is remade."""
    out = {}
    for path in sorted(glob.glob(os.path.join(COURSES, "*.geojson"))):
        slug = os.path.basename(path)[:-len(".geojson")]
        course, _ = load_course(slug, _published_course(slug))
        out[slug] = (course, guide(course))
    return out


# ---------------------------------------------------------------------------------------------- markers


def town_name(name: str) -> str:
    """OpenStreetMap sometimes glues two words together ("BimponAgya")."""
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)


def towns(settlements: gpd.GeoDataFrame, line: LineString, water: LineString | None = None) -> list[dict]:
    """Villages within 1.5 km of the river and towns within 5 km (the page pins those outside the picture to its edge
    with their distance), in order down the river. km and off_m place them on the picture (`line`, the guide);
    water_m is how far they are from the river itself (`water`, the course)."""
    water = water or line
    s = settlements[settlements["name"].notna()]
    d = s.distance(water)
    keep = ((s.place == "village") & (d < 1500)) | (s.place.isin(["city", "town"]) & (d < 5000))
    s, d = s[keep], d[keep]
    lon, lat = TO_LL.transform(s.geometry.x.to_numpy(), s.geometry.y.to_numpy())
    # lon/lat: posts name a town only within 2 km of a patch on the ground (studio posts/rivers.ts)
    out = [{"name": town_name(t["name"]), "place": t.place, "km": round(line.project(t.geometry) / 1000, 2),
            "off_m": offset(line, t.geometry), "water_m": round(float(dm)), "lon": round(float(x), 5),
            "lat": round(float(y), 5)} for (_, t), dm, x, y in zip(s.iterrows(), d, lon, lat)]
    return sorted(out, key=lambda t: t["km"])


def river_places(geoms: gpd.GeoSeries, rivers: dict) -> list[list[dict]]:
    """For each place, the walked rivers whose water is within 1 km of it, nearest first: picture km (the page's
    #km-N), bank offset, distance to the water, and whether it lies inside the 2 km picture (the river winds up to
    about 500 m off the picture's middle, so a patch near the water can sit just past its edge)."""
    geoms = geoms.reset_index(drop=True)
    out = [[] for _ in range(len(geoms))]
    for slug, (course, g) in rivers.items():
        # the spatial index finds the few places near this river; only those are measured (about 1 in 8)
        for i in sorted(geoms.sindex.query(course, predicate="dwithin", distance=NEAR_M)):
            d = geoms.iloc[i].distance(course)
            if d >= NEAR_M:
                continue
            c = geoms.iloc[i].representative_point()
            off = offset(g, c)
            out[i].append({"slug": slug, "km": round(g.project(c) / 1000, 3), "off_m": off,
                           "river_m": round(float(d)), "in_picture": abs(off) <= HALF_M})
    return [sorted(o, key=lambda r: r["river_m"]) for o in out]


def _plants(course: LineString, g: LineString) -> list[dict]:
    p = water.load()
    pts = gpd.GeoSeries(gpd.points_from_xy(p.plant_lon, p.plant_lat), crs=4326).to_crs(WORK_CRS)
    return sorted(({"name": n, "km": round(g.project(pt) / 1000, 2)} for n, pt in zip(p["plant"], pts)
                   if pt.distance(course) < 1500), key=lambda x: x["km"])


def _join_marks(joins: list[dict], g: LineString) -> list[dict]:
    def pt(ll):
        return Point(TO_M.transform(*ll))

    out = [{"name": j["name"], "slug": j["slug"], "km": round(g.project(pt(j["at"])) / 1000, 2),
            "side": "left" if offset(g, pt(j["up"])) > 0 else "right"} for j in joins]
    return sorted(out, key=lambda j: j["km"])


# ---------------------------------------------------------------------------------------------- pictures


def cloud_mask(rgb: np.ndarray) -> np.ndarray:
    """Cloud by colour: bright and colourless, widened by 40 m for the soft edge. A pale sand pit can pass for cloud
    too, which costs nothing: it is replaced by the same ground from another day."""
    from scipy.ndimage import binary_dilation
    mn, mx = rgb.min(axis=2).astype(int), rgb.max(axis=2).astype(int)
    return binary_dilation((mn > 150) & ((mx - mn) < 45), iterations=4)


def _middle(h: int, w: int) -> np.ndarray:
    yy, xx = np.mgrid[:h, :w]
    return np.hypot((yy - h / 2) / h, (xx - w / 2) / w) * 2 * CROP_HALF_KM * 1000 < MIDDLE_M


def pick_day(days: list[tuple[str, float]], prev: str | None) -> str | None:
    """The day to use for a crop, from (day, clear share of the middle). The newest clear day, so the walk shows
    the river as recently as the weather allows. The piece above's day is kept if it is clear and not much older:
    one satellite pass covers a long way, and keeping it leaves no seam. With no clear day, the clearest."""
    if not days:
        return None
    clear = sorted((d for d, c in days if c >= CLEAR), reverse=True)
    if not clear:
        return max(days, key=lambda x: x[1])[0]
    if prev in clear and (dt.date.fromisoformat(clear[0]) - dt.date.fromisoformat(prev)).days <= SAME_PASS_DAYS:
        return prev
    return clear[0]


_pool = ThreadPoolExecutor(2)


def _read_day(item, bbox, h=None, w=None):
    """True colour and its usable pixels for one day, or None if it cannot be read. The picture and its cloud layer
    download at the same time."""
    try:
        visual, scl = (f.result() for f in [_pool.submit(chips._read, item.assets[k].href, bbox) for k in ("visual", "scl")])
        cand = np.moveaxis(visual, 0, -1)
        h, w = h or cand.shape[0], w or cand.shape[1]
        scl = np.array(Image.fromarray(scl[0]).resize((w, h), Image.NEAREST))
    except Exception as e:  # noqa: BLE001  a broken or slow file: the next day is tried
        print("   skip", type(e).__name__, flush=True)
        return None
    if cand.shape[:2] != (h, w):
        cand = np.array(Image.fromarray(cand).resize((w, h), Image.BILINEAR))
    ok = ~np.isin(scl, chips.CLOUDY_SCL) & (scl != 0) & ~cloud_mask(cand) & (cand.sum(axis=2) > 0)
    return cand, ok


def crop(lon: float, lat: float, start: dt.date, end: dt.date, prev: str | None):
    """(day, HxWx3) for the 4.6 km crop around a point: the day pick_day chooses, its remaining cloud filled from
    the other days read (only their clear pixels, scaled to the main day's colour). None if nothing could be read."""
    bbox = chips._bbox(lon, lat, CROP_HALF_KM)
    items = sorted(chips.search(bbox, start, end, 60), key=lambda i: i.datetime, reverse=True)
    items = [i for i in items if str(i.datetime.date()) == prev] + [i for i in items if str(i.datetime.date()) != prev]
    # keyed by scene: a crop near the edge of two satellite tiles can have two scenes from one day, each covering part
    read, h, w, mid = {}, None, None, None
    for item in items[:TRIES]:
        got = _read_day(item, bbox, h, w)
        if got is None:
            continue
        h, w = got[0].shape[:2]
        mid = _middle(h, w) if mid is None else mid
        day = str(item.datetime.date())
        read[item.id] = (*got, float((got[1] & mid).sum() / mid.sum()), day)
        if read[item.id][2] >= CLEAR and day != prev:
            break   # newest clear day found (days are read newest first, after the piece above's)
    if items and not read:
        # every day failed to download (a slow or refused connection): an error, so the caller waits and retries
        raise OSError(f"none of {min(len(items), TRIES)} days could be read")
    day = pick_day([(v[3], v[2]) for v in read.values()], prev)
    if day is None:
        return None
    main = max((k for k, v in read.items() if v[3] == day), key=lambda k: read[k][2])
    rgb, ok, _, _ = read[main]
    rgb = rgb.copy()
    need = ~ok & mid
    for other in sorted(read, key=lambda k: -read[k][2]):
        if other == main or need.sum() < 0.0005 * h * w:
            continue
        cand, ok2, _, _ = read[other]
        both = ok & ok2 & mid
        if both.sum() < 2000:
            continue
        gain = np.clip(np.median(rgb[both].astype(float), axis=0) / np.maximum(np.median(cand[both].astype(float), axis=0), 1), 0.6, 1.6)
        put = need & ok2
        rgb[put] = np.clip(cand[put] * gain, 0, 255).astype(np.uint8)
        need &= ~put
    return day, rgb


def _sample(rgb, lon, lat, pts_ll):
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = chips._bbox(lon, lat, CROP_HALF_KM)
    cx = ((pts_ll[:, 0] - x0) / (x1 - x0) * w).astype(int)
    cy = ((y1 - pts_ll[:, 1]) / (y1 - y0) * h).astype(int)
    ok = (cx >= 0) & (cx < w) & (cy >= 0) & (cy < h)
    out = np.full((len(pts_ll), 3), 235, np.uint8)
    out[ok] = rgb[cy[ok], cx[ok]]
    return out, ok


def _cached(cache: str | None, lon: float, lat: float):
    """A crop saved by an earlier try of the same run (or a local copy), if its centre is within 700 m."""
    if not cache or not os.path.isdir(cache):
        return None
    best, bd = None, 700.0
    for f in os.listdir(cache):
        x, y = map(float, f[:-4].split("_")[:2])
        d = math.hypot((x - lon) * 110600, (y - lat) * 110600)
        if d < bd:
            best, bd = (f, x, y), d
    if best is None:
        return None
    z = np.load(os.path.join(cache, best[0]))
    return str(z["day"]), z["rgb"], best[1], best[2]


def picture(g: LineString, start: dt.date, end: dt.date, cache: str | None = None) -> tuple[np.ndarray, list]:
    """The whole picture, one row per 10 m of guide line, and each 2.5 km chunk's day."""
    n = int(g.length // STEP_M)
    img = np.full((n, 2 * HALF_M // STEP_M, 3), 235, np.uint8)
    per = CHUNK_M // STEP_M
    shots = []
    for c0 in range(0, n, per):
        p = g.interpolate(min(g.length, (c0 + per / 2) * STEP_M))
        lon, lat = TO_LL.transform(p.x, p.y)
        shot = _cached(cache, lon, lat)
        if shot is None:
            prev = next((s[0] for s in reversed(shots) if s), None)
            got = None
            # the last 12 months first; a stretch with no usable day in them (rare) looks back a year more
            for since in (start, start - dt.timedelta(days=LOOKBACK_DAYS)):
                for wait in (*RETRY_WAITS, None):
                    try:
                        got = crop(lon, lat, since, end, prev)
                        break
                    except (OSError, APIError) as e:
                        if wait is None:
                            break
                        print("   retry", type(e).__name__, e, flush=True)
                        time.sleep(wait)
                if got:
                    break
            shot = (got[0], got[1], lon, lat) if got else None
            if shot and cache:
                os.makedirs(cache, exist_ok=True)
                np.savez_compressed(os.path.join(cache, f"{lon:.5f}_{lat:.5f}.npz"), rgb=shot[1], day=shot[0])
        print(f"   km {c0 * STEP_M / 1000:.1f}", shot[0] if shot else "-", flush=True)
        shots.append(shot)
    if missing := [i * CHUNK_M / 1000 for i, s in enumerate(shots) if s is None]:
        # a grey gap in a published walk is worse than keeping the last pictures: stop, and the run keeps them
        raise RuntimeError(f"no picture for the stretches starting at km {missing}")
    half = BLEND_M // STEP_M // 2
    for row in range(n):
        ci = min(row // per, len(shots) - 1)
        pts = np.c_[TO_LL.transform(*band_points(g, row * STEP_M).T)]
        pos, mine = row - ci * per, shots[ci]
        val, ok = _sample(mine[1], mine[2], mine[3], pts)
        other = None
        if pos < half and ci > 0:
            other, wt = shots[ci - 1], 0.5 - (pos + 0.5) / (2 * half)
        elif pos >= per - half and ci + 1 < len(shots):
            other, wt = shots[ci + 1], 0.5 - (per - pos - 0.5) / (2 * half)
        if other:
            v2, ok2 = _sample(other[1], other[2], other[3], pts)
            both = ok & ok2
            val = val.astype(float)
            val[both] = val[both] * (1 - wt) + v2[both] * wt
            val[~ok & ok2] = v2[~ok & ok2]
            val = val.astype(np.uint8)
        img[row] = val
    return img, [s[0] for s in shots]


def build(slug: str, today: dt.date, cache: str | None = None) -> dict:
    """Pictures and data for one river. The version is the time of the run (UTC, to the minute), so a new set never
    reuses the address of tiles a browser or the pictures site already keeps for a year."""
    cfg = config()[slug]
    course, props = load_course(slug)
    g = guide(course)
    version = dt.datetime.now(dt.UTC).strftime("%Y%m%d%H%M")
    start = today - dt.timedelta(days=LOOKBACK_DAYS)
    img, days = picture(g, start, today, cache)
    rows = tile_rows(img.shape[0])
    tiles_dir = os.path.join(OUT, "rivers", slug, version)
    os.makedirs(tiles_dir, exist_ok=True)
    # the course these tiles follow travels with them, so the weekly run places patches on the same line (lines())
    shutil.copyfile(os.path.join(COURSES, f"{slug}.geojson"), os.path.join(tiles_dir, "course.json"))
    per = CHUNK_M // STEP_M
    tiles = []
    for i, (r0, r1) in enumerate(rows):
        Image.fromarray(img[r0:r1]).save(os.path.join(tiles_dir, f"tile-{i:03d}.webp"), quality=82, method=6)
        # each tile's rows, days and cloud: the page sizes its boxes and the posts date their slices from these
        tiles.append({"rows": r1 - r0, "days": sorted(set(days[r0 // per:-(-r1 // per)])),
                      "cloud": round(float(cloud_mask(img[r0:r1]).mean()), 3)})
    z = gpd.GeoSeries([zone.load()], crs=4326).to_crs(WORK_CRS).iloc[0]
    simple = np.array(course.simplify(200).coords)
    meta = {
        "slug": slug, "name": cfg["name"], "ends": cfg["ends"], "joins_to": cfg.get("joins_to"), "version": version,
        "visible_km2": cfg.get("visible_km2", 500),
        "length_km": round(img.shape[0] * STEP_M / 1000, 2), "river_km": round(course.length / 1000, 1),
        "streams_km": props["streams_km"], "step_m": STEP_M, "half_m": HALF_M, "width": img.shape[1],
        "tile_km": TILE_KM, "km_left": km_left(course, g),
        "course": [[round(x, 4), round(y, 4)] for x, y in zip(*TO_LL.transform(simple[:, 0], simple[:, 1]))],
        "towns": towns(places.settlements(os.path.join(CACHE, "places")).to_crs(WORK_CRS), g, course),
        "joins": _join_marks(props["joins"], g), "plants": _plants(course, g),
        "zone_end_km": zone_end_km([z.contains(g.interpolate(d)) for d in np.arange(0, g.length, 500)]),
        "tiles": tiles, "dates": sorted(set(days)),
    }
    # beside its tiles, so the two are always saved and restored together (rivers.yml, rivers-state release)
    write_json(os.path.join(OUT, "rivers", f"{slug}.json"), meta)
    print(f"{slug}: {meta['length_km']} km of picture, {len(rows)} tiles, days {meta['dates'][:1]} to {meta['dates'][-1:]}")
    return meta
