"""Rivers pilot: a river from its source to the sea (or to the river it joins), as it looks now.

The course: HydroRIVERS main stem walked upstream from the mouth. At each fork it takes the branch that lies on the
OSM line with the river's name, so a bigger tributary cannot steal the walk. The course is then pulled onto the OSM
line where that line is close (HydroRIVERS follows a 500 m grid and wanders off the channel), and smoothed.
The picture: one row, the newest clear dry season, 1 km either side, sampled every 10 m, read top (source) to
bottom (sea), west bank on the left for a river flowing south. Seams between pictures are blended over 200 m.
Cut into 5 km WebP tiles for the page; markers (towns, rivers joining, plants, cleared places) with km and offset.

Run from the repo root: uv run --project pipeline python spike/river_walk.py <slug> [course]
"""
import datetime as dt
import json
import os
import re
import sys
import time

import geopandas as gpd
import numpy as np
from PIL import Image
from shapely.geometry import LineString, Point
from shapely.ops import linemerge, substring

sys.path.insert(0, "pipeline")
from tracker import chips  # noqa: E402

RIVERS = "pipeline/out/cache/hydro/rivers_ghana.gpkg"
OSM = "pipeline/out/cache/osm/ghana.osm.pbf"
CRS = 32630
STEP_M = 10
HALF_M = 1000
CHUNK_M = 2500
CROP_HALF_KM = 2.3          # holds the band around a chunk even where the river bends
BLEND_M = 200
TILE_KM = 5
EPOCHS = [(dt.date(2025, 11, 1), dt.date(2026, 3, 15)), (dt.date(2024, 11, 1), dt.date(2025, 3, 31)),
          (dt.date(2023, 11, 1), dt.date(2024, 3, 31))]
# slug: (name, a point on the river near its lower end lon/lat, where it ends). The walk goes down from the
# point until the river reaches the sea or joins a much larger river, then back up the main stem.
RIVER = {
    "pra": ("Pra", (-1.619, 5.027), "the sea at Shama"),
    "ankobra": ("Ankobra", (-2.281, 4.906), "the sea near Axim"),
    "densu": ("Densu", (-0.315, 5.510), "the sea west of Accra"),
    "ayensu": ("Ayensu", (-0.590, 5.360), "the sea east of Winneba"),
    "offin": ("Offin", (-1.783, 5.962), "the Pra"),      # Dunkwa-on-Offin
    "birim": ("Birim", (-0.997, 5.920), "the Pra"),      # Oda
}
OUT = "pipeline/out/checks/rivers"


def tried(fn, *a, attempts=4):
    for k in range(attempts):
        try:
            return fn(*a)
        except Exception as e:  # noqa: BLE001
            print("   retry", type(e).__name__, flush=True)
            time.sleep(20 * (k + 1))
    return None


def osm_line(name):
    lines = gpd.read_file(OSM, layer="lines", where="waterway IN ('river', 'stream')").to_crs(CRS)
    pat = re.compile(rf"^(river\s+)?{name}(\s+river)?$", re.I)
    named = lines[lines["name"].fillna("").str.strip().str.match(pat)]
    print(f"OSM {name}: {len(named)} ways, {named.length.sum() / 1000:.0f} km", flush=True)
    return named.union_all()


def course(slug):
    name, mouth, _ = RIVER[slug]
    r = gpd.read_file(RIVERS).to_crs(CRS).set_index("HYRIV_ID")
    osm = osm_line(name)
    big = r[r.UPLAND_SKM > 300]
    start = big.distance(gpd.GeoSeries([Point(mouth)], crs=4326).to_crs(CRS).iloc[0]).idxmin()
    while r.loc[start].NEXT_DOWN in r.index and r.loc[r.loc[start].NEXT_DOWN].UPLAND_SKM < 1.6 * r.loc[start].UPLAND_SKM:
        start = r.loc[start].NEXT_DOWN
    osm = osm if osm.length > 0.5 * r.loc[start].DIST_UP_KM * 1000 else None   # a short named line cannot guide
    ups = r.groupby("NEXT_DOWN").groups
    chain, rid = [], start
    while True:
        chain.append(rid)
        kids = list(ups.get(rid, []))
        if not kids:
            break
        # the branch on the named line; if none is near it, the larger one
        on = [k for k in kids if osm is not None and r.loc[k].geometry.distance(osm) < 500]
        rid = max(on or kids, key=lambda k: r.loc[k].UPLAND_SKM)
        if not on and r.loc[rid].UPLAND_SKM < 30:
            break
    parts = [r.loc[k].geometry for k in reversed(chain)]   # source first
    rough = linemerge(parts)
    # snap targets: the named line plus unnamed river ways along the course (OSM often leaves stretches unnamed)
    ways = gpd.read_file(OSM, layer="lines", where="waterway = 'river' AND name IS NULL").to_crs(CRS)
    ways = ways[ways.distance(rough) < 1000]
    targets = [g for g in [osm] if g is not None and not g.is_empty] + list(ways.geometry)
    snap_to = gpd.GeoSeries(targets, crs=CRS).union_all() if targets else None
    line = linemerge(parts)
    line = LineString([c for g in getattr(line, "geoms", [line]) for c in g.coords])
    pts = [line.interpolate(d) for d in np.arange(0, line.length, 25)]
    # pull onto OSM where it is within 1 km; snapped stretches keep their meanders (100 m smoothing),
    # HydroRIVERS-only stretches are smoothed over 500 m so the 500 m grid does not kink the picture
    snapped, on = [], []
    for p in pts:
        q = nearest_on(snap_to, p) if snap_to is not None else p
        ok = p.distance(q) < 1000
        snapped.append(q if ok else p)
        on.append(ok)
    xy = np.array([(p.x, p.y) for p in snapped])

    def smooth(a, k):
        pad = np.pad(a, ((k // 2, k // 2), (0, 0)), mode="edge")
        return np.stack([np.convolve(pad[:, i], np.ones(k) / k, mode="valid") for i in (0, 1)], axis=1)

    w = np.convolve(np.array(on, float), np.ones(21) / 21, mode="same")[:, None]   # ease between the two
    xy = w * smooth(xy, 5) + (1 - w) * smooth(xy, 21)
    out = LineString(xy)
    print(f"{slug}: {out.length / 1000:.1f} km, {len(chain)} reaches", flush=True)
    return out, (r, chain)


def nearest_on(geom, p):
    from shapely.ops import nearest_points
    return nearest_points(geom, p)[0]


def band_points(line, d):
    p, q = line.interpolate(d), line.interpolate(min(d + STEP_M, line.length))
    if d + STEP_M > line.length:
        p, q = line.interpolate(d - STEP_M), line.interpolate(d)
    t = np.array([q.x - p.x, q.y - p.y])
    t /= np.linalg.norm(t) or 1
    right = np.array([t[1], -t[0]])          # right bank when looking downstream (west for a south-flowing river)
    cols = 2 * HALF_M // STEP_M
    offs = HALF_M - (np.arange(cols) + 0.5) * STEP_M   # screen left = right bank
    c = line.interpolate(d)
    return np.array([c.x, c.y]) + offs[:, None] * right[None, :]


def sample(shot, lon, lat, pts_ll):
    rgb = shot[1]
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = chips._bbox(lon, lat, CROP_HALF_KM)
    cx = ((pts_ll[:, 0] - x0) / (x1 - x0) * w).astype(int)
    cy = ((y1 - pts_ll[:, 1]) / (y1 - y0) * h).astype(int)
    ok = (cx >= 0) & (cx < w) & (cy >= 0) & (cy < h)
    out = np.full((len(pts_ll), 3), 235, np.uint8)
    out[ok] = rgb[cy[ok], cx[ok]]
    return out, ok


def _cache_dir(slug):
    d = f"{OUT}/{slug}/crops"
    os.makedirs(d, exist_ok=True)
    return d


def cached(slug, mid):
    """A crop already downloaded whose centre is within 500 m of this one (the crop is 4.6 km across)."""
    for f in os.listdir(_cache_dir(slug)):
        lon, lat = map(float, f[:-4].split("_")[:2])
        if abs(lon - mid.x) * 111000 < 500 and abs(lat - mid.y) * 111000 < 500:
            z = np.load(f"{_cache_dir(slug)}/{f}")
            return (str(z["day"]), z["rgb"], (lon, lat))
    return None


def keep(slug, mid, shot):
    np.savez_compressed(f"{_cache_dir(slug)}/{mid.x:.5f}_{mid.y:.5f}.npz", rgb=shot[1], day=str(shot[0]))


def picture(slug, line):
    n = int(line.length // STEP_M)
    cols = 2 * HALF_M // STEP_M
    img = np.full((n, cols, 3), 235, np.uint8)
    to_ll = lambda a: np.array(gpd.GeoSeries(gpd.points_from_xy(a[:, 0], a[:, 1]), crs=CRS).to_crs(4326).apply(lambda g: (g.x, g.y)).tolist())
    per = CHUNK_M // STEP_M
    shots, dates = [], []
    for c0 in range(0, n, per):
        mid = gpd.GeoSeries([line.interpolate(min(line.length, (c0 + per / 2) * STEP_M))], crs=CRS).to_crs(4326).iloc[0]
        shot = cached(slug, mid)
        if shot is None:
            for start, end in EPOCHS:
                shot = tried(chips.clearest, mid.x, mid.y, CROP_HALF_KM, start, end)
                if shot:
                    break
            if shot:
                keep(slug, mid, shot)
        else:
            mid = gpd.GeoSeries([Point(shot[2])], crs=4326).iloc[0]   # the crop's own centre
        print(slug, f"km {c0 * STEP_M / 1000:.1f}", shot[0] if shot else "-", flush=True)
        shots.append((shot, mid.x, mid.y))
        dates.append(str(shot[0]) if shot else None)
    half = BLEND_M // STEP_M // 2
    for row in range(n):
        ci = min(row // per, len(shots) - 1)
        pts = to_ll(band_points(line, row * STEP_M))
        pos = row - ci * per
        mine = shots[ci]
        val, ok = sample(mine[0], mine[1], mine[2], pts) if mine[0] else (None, None)
        other = None
        if pos < half and ci > 0:
            other, wt = shots[ci - 1], 0.5 - (pos + 0.5) / (2 * half)
        elif pos >= per - half and ci + 1 < len(shots):
            other, wt = shots[ci + 1], 0.5 - (per - pos - 0.5) / (2 * half)
        if other and other[0]:
            v2, ok2 = sample(other[0], other[1], other[2], pts)
            if val is None:
                val, ok = v2, ok2
            else:
                both = ok & ok2
                val = val.astype(float)
                val[both] = val[both] * (1 - wt) + v2[both] * wt
                val[~ok & ok2] = v2[~ok & ok2]
                val = val.astype(np.uint8)
        if val is not None:
            img[row] = val
    return img, dates


def markers(slug, line, reaches):
    ll = lambda g: gpd.GeoSeries([g], crs=CRS)
    out = {"towns": [], "joins": [], "plants": [], "places": []}
    s = gpd.read_file("pipeline/out/cache/places/settlements_ghana.geojson").to_crs(CRS)
    s = s[s.place.isin(["city", "town", "village"]) & (s.distance(line) < 1500) & s["name"].notna()]
    for _, t in s.iterrows():
        d = line.project(t.geometry)
        out["towns"].append({"name": t["name"], "place": t.place, "km": round(d / 1000, 2), "off_m": round(offset(line, t.geometry))})
    # rivers joining: HydroRIVERS branches draining at least 400 km2, named from OSM or from the RIVER list
    r, chain = reaches
    named = gpd.read_file(OSM, layer="lines", where="waterway = 'river' AND name IS NOT NULL").to_crs(CRS)
    seeds = {v[0]: gpd.GeoSeries([Point(v[1])], crs=4326).to_crs(CRS).iloc[0] for k, v in RIVER.items() if k != slug}
    on = set(chain)
    for k in r.index[r.NEXT_DOWN.isin(on) & ~r.index.isin(on) & (r.UPLAND_SKM >= 400)]:
        # follow this branch up a little to name it
        trunk, rid = [k], k
        for _ in range(40):
            kids = r.index[r.NEXT_DOWN == rid]
            if not len(kids):
                break
            rid = r.loc[kids].UPLAND_SKM.idxmax()
            trunk.append(rid)
        geom = linemerge([r.loc[i].geometry for i in trunk])
        nm = next((n for n, p in seeds.items() if p.distance(geom) < 3000), None)
        if not nm:
            near = named[(named.distance(r.loc[k].geometry) < 1500) & ~named["name"].str.contains(RIVER[slug][0], case=False)]
            nm = near["name"].mode().iloc[0] if len(near) else None
        end = Point(r.loc[k].geometry.coords[-1])
        out["joins"].append({"name": nm, "km": round(line.project(end) / 1000, 2), "upland_km2": round(float(r.loc[k].UPLAND_SKM))})
    plants = gpd.read_file("pipeline/water_plants.geojson").to_crs(CRS)
    pts = gpd.GeoSeries(gpd.points_from_xy(plants.plant_lon, plants.plant_lat), crs=4326).to_crs(CRS)
    for (_, p), pt in zip(plants.iterrows(), pts):
        if pt.distance(line) < 1500:
            out["plants"].append({"name": p["plant"], "km": round(line.project(pt) / 1000, 2)})
    pl = gpd.read_file("pipeline/out/places/latest.geojson").to_crs(CRS)
    idx = json.load(open("pipeline/out/places/index.json", encoding="utf-8"))
    pl = pl[pl.distance(line) < HALF_M]
    for _, p in pl.iterrows():
        c = p.geometry.representative_point()
        i = idx.get(p["id"], {})
        out["places"].append({"id": p["id"], "km": round(line.project(c) / 1000, 3), "off_m": round(offset(line, c)),
                              "ha": i.get("ha"), "licence": i.get("licence"), "likely": bool(i.get("likely_galamsey")),
                              "near": i.get("near"), "near_km": i.get("near_km")})
    for k in out:
        out[k].sort(key=lambda m: m["km"])
    return out


def offset(line, pt):
    """Metres across the band, positive to screen left (the right bank)."""
    d = line.project(pt)
    c = line.interpolate(d)
    q = line.interpolate(min(line.length, d + STEP_M))
    t = np.array([q.x - c.x, q.y - c.y])
    t /= np.linalg.norm(t) or 1
    right = np.array([t[1], -t[0]])
    return float(np.dot([pt.x - c.x, pt.y - c.y], right))


def run(slug, only_course=False):
    out = f"{OUT}/{slug}"
    os.makedirs(out, exist_ok=True)
    line, reaches = course(slug)
    gpd.GeoSeries([line], crs=CRS).to_crs(4326).to_file(f"{out}/course.geojson")
    m = markers(slug, line, reaches)
    simple = gpd.GeoSeries([line.simplify(200)], crs=CRS).to_crs(4326).iloc[0]
    meta = {"slug": slug, "name": RIVER[slug][0], "ends": RIVER[slug][2], "length_km": round(line.length / 1000, 1),
            "step_m": STEP_M, "half_m": HALF_M, "tile_km": TILE_KM, "course": [[round(x, 4), round(y, 4)] for x, y in simple.coords],
            **m}
    json.dump(meta, open(f"{out}/river.json", "w", encoding="utf-8"), indent=1)
    print({k: len(v) for k, v in m.items()}, flush=True)
    if only_course:
        return
    img, dates = picture(slug, line)
    meta["dates"] = sorted({d for d in dates if d})
    json.dump(meta, open(f"{out}/river.json", "w", encoding="utf-8"), indent=1)
    Image.fromarray(img).save(f"{out}/strip.png")
    rows = TILE_KM * 1000 // STEP_M
    for i, r0 in enumerate(range(0, img.shape[0], rows)):
        Image.fromarray(img[r0:r0 + rows]).save(f"{out}/tile-{i:03d}.webp", quality=82, method=6)


if __name__ == "__main__":
    run(sys.argv[1], only_course=sys.argv[2:] == ["course"])
