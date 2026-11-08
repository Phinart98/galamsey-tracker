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
BLEND_M = 500
VISIBLE_KM2 = 500        # start where the river drains this much: above it the river is narrower than a 10 m pixel
ALIASES = {"Offin": ["Ofin"], "Pra": ["Prah"]}   # other spellings in OSM
VISIBLE = {"densu": 200, "ayensu": 200}   # small coastal rivers: a lower bar, or most of them would be cut
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
    names = "|".join([name] + ALIASES.get(name, []))
    pat = re.compile(rf"^(river\s+)?({names})(\s+river)?$", re.I)
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
    raw = np.array([(p.x, p.y) for p in pts])
    shift = np.array([(q.x - p.x, q.y - p.y) for p, q in zip(pts, snapped)])
    # a snap that hops onto a side channel or the other arm of a bend for a short way is a jump in the shift:
    # a running median over 2 km drops it (sharp sideways turns on the Pra: 75 without, 6 with), so the course moves sideways only where the river really does
    from scipy.ndimage import median_filter
    shift = np.stack([median_filter(shift[:, i], size=81, mode="nearest") for i in (0, 1)], axis=1)
    xy = raw + shift

    def smooth(a, k):
        pad = np.pad(a, ((k // 2, k // 2), (0, 0)), mode="edge")
        return np.stack([np.convolve(pad[:, i], np.ones(k) / k, mode="valid") for i in (0, 1)], axis=1)

    w = np.convolve(np.array(on, float), np.ones(21) / 21, mode="same")[:, None]   # ease between the two
    xy = w * smooth(xy, 5) + (1 - w) * smooth(xy, 21)
    out = LineString(xy)
    # where the river becomes visible: the upstream end of the highest reach draining VISIBLE_KM2
    big = [k for k in chain if r.loc[k].UPLAND_SKM >= VISIBLE.get(slug, VISIBLE_KM2)]
    cut = out.project(Point(r.loc[big[-1]].geometry.coords[0])) if big else 0.0
    streams_km = cut / 1000
    out = substring(out, cut, out.length)
    print(f"{slug}: {out.length / 1000:.1f} km shown, {streams_km:.1f} km of streams above, {len(chain)} reaches, "
          f"{jumps(out)} sideways jumps", flush=True)
    return out, (r, chain), streams_km


GUIDE_K = 81   # 2 km box smoothing, twice: the band follows the valley, the river snakes inside it


def guide(line):
    """The line the picture is cut along: the course smoothed over about 2 km.

    Cut square to the exact course, the cross-lines fold over each other inside every bend tighter than the
    band (about 3 in 10 rows), which smears and repeats ground. Cut along this smoother line they almost never
    fold, and the river winds inside the band (at most about 500 m off the middle) the way it looks from above.
    Guide point i is the average of course points around i, so it sits at exactly 25 m x i of river."""
    xy = np.array([line.interpolate(d).coords[0] for d in np.arange(0, line.length, 25)] + [line.coords[-1]])
    box = lambda a: np.stack([np.convolve(np.pad(a[:, i], GUIDE_K // 2, mode="edge"), np.ones(GUIDE_K) / GUIDE_K, mode="valid") for i in (0, 1)], axis=1)
    g = box(box(xy))
    along = np.minimum(np.arange(len(xy)) * 25.0, line.length)
    dev = np.linalg.norm(xy - g, axis=1)
    print(f"guide: {LineString(g).length / 1000:.1f} km of picture, river at most {dev.max():.0f} m off the middle", flush=True)
    return LineString(g), along


def jumps(line):
    """Places where the course turns more than 60 degrees within 50 m: what reads as a cut in the picture."""
    xy = np.array([line.interpolate(d).coords[0] for d in np.arange(0, line.length, 25)])
    h = np.arctan2(np.diff(xy[:, 1]), np.diff(xy[:, 0]))
    turn = np.abs((h[2:] - h[:-2] + np.pi) % (2 * np.pi) - np.pi)
    return int((np.diff((turn > np.radians(60)).astype(int)) == 1).sum())


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
    d = f"{OUT}/{slug}/crops2"
    os.makedirs(d, exist_ok=True)
    return d


def cached(slug, mid):
    """The nearest crop already downloaded, if its centre is within 700 m of this one. The crop is 4.6 km across,
    so it still covers a 2.5 km piece of the 2 km band with room to spare."""
    best, bd = None, 700.0
    for f in os.listdir(_cache_dir(slug)):
        lon, lat = map(float, f[:-4].split("_")[:2])
        d = np.hypot((lon - mid.x) * 110600, (lat - mid.y) * 110600)
        if d < bd:
            best, bd = (f, lon, lat), d
    if best is None:
        return None
    z = np.load(f"{_cache_dir(slug)}/{best[0]}")
    return (str(z["day"]), z["rgb"], (best[1], best[2]))


def keep(slug, mid, shot):
    np.savez_compressed(f"{_cache_dir(slug)}/{mid.x:.5f}_{mid.y:.5f}.npz", rgb=shot[1], day=str(shot[0]))


def cloud_mask(rgb):
    """Cloud by colour: bright and colourless, widened by 40 m for the soft edge. A pale sand pit can pass for
    cloud too, which costs nothing: it is replaced by the same ground from another day."""
    from scipy.ndimage import binary_dilation
    mn, mx = rgb.min(axis=2).astype(int), rgb.max(axis=2).astype(int)
    return binary_dilation((mn > 150) & ((mx - mn) < 45), iterations=4)


def fill(slug, tries=5):
    """Cloud in the middle of a cached crop (the part the picture uses) is filled from the next clearest days of
    the same spot. Only that day's clear pixels are used, scaled to the main day's colour."""
    d = _cache_dir(slug)
    for f in sorted(os.listdir(d)):
        z = dict(np.load(f"{d}/{f}"))
        if "filled" in z:
            continue
        rgb = z["rgb"].copy()
        h, w = rgb.shape[:2]
        yy, xx = np.mgrid[:h, :w]
        mid = np.hypot((yy - h / 2) / h, (xx - w / 2) / w) * 2 * CROP_HALF_KM * 1000 < 1700
        need = cloud_mask(rgb) & mid
        start_frac, used, read = need.mean(), [], 0
        if need.sum() > 0.003 * h * w:
            lon, lat = map(float, f[:-4].split("_")[:2])
            bbox = chips._bbox(lon, lat, CROP_HALF_KM)
            items = [i for start, end in EPOCHS for i in tried(chips.search, bbox, start, end, 40)]
            items = [i for i in items if str(i.datetime.date()) != str(z["day"])]
            for item in items:
                if need.sum() < 0.0005 * h * w or read >= tries:
                    break
                read += 1
                try:
                    scl = np.array(Image.fromarray(chips._read(item.assets["scl"].href, bbox)[0]).resize((w, h), Image.NEAREST))
                    cand = np.moveaxis(chips._read(item.assets["visual"].href, bbox), 0, -1)
                except Exception as e:  # noqa: BLE001  a broken or slow file: try the next day
                    print("   skip", type(e).__name__, flush=True)
                    continue
                if cand.shape[:2] != (h, w):
                    cand = np.array(Image.fromarray(cand).resize((w, h), Image.BILINEAR))
                ok = ~np.isin(scl, chips.CLOUDY_SCL) & (scl != 0) & ~cloud_mask(cand) & (cand.sum(axis=2) > 0)
                both = ok & ~cloud_mask(rgb) & mid
                if both.sum() < 2000:
                    continue
                gain = np.clip(np.median(rgb[both].astype(float), axis=0) / np.maximum(np.median(cand[both].astype(float), axis=0), 1), 0.6, 1.6)
                put = need & ok
                rgb[put] = np.clip(cand[put] * gain, 0, 255).astype(np.uint8)
                need &= ~put
                used.append(str(item.datetime.date()))
        np.savez_compressed(f"{d}/{f}", rgb=rgb, day=str(z["day"]), filled=np.array(used or ["none"]))
        print(slug, f, f"cloud {start_frac * 100:.1f}% -> {need.mean() * 100:.1f}%", used, flush=True)


def swap(slug, over=1.5, tries=6):
    """Filling only the bright cores of a cloud leaves the thin haze around them, so each filled core shows as a
    crisp island in grey. For crops that were more than `over` % cloud (read from the fill log), the whole middle
    is replaced by one day that is clear over nearly all of it, feathered at the edge of the middle (outside the
    band the picture uses). The crop's day becomes that day, so the page's dates stay true."""
    from scipy.ndimage import gaussian_filter
    d = _cache_dir(slug)
    with open(f"{OUT}/{slug}-fill.log", encoding="utf-8") as log:
        bad = [ln.split()[1] for ln in log
               if ln.startswith(slug + " ") and " cloud " in ln and float(ln.split()[3].rstrip("%")) > over]
    for f in bad:
        z = dict(np.load(f"{d}/{f}"))
        if "swapped" in z:
            continue
        rgb = z["rgb"].copy()
        h, w = rgb.shape[:2]
        yy, xx = np.mgrid[:h, :w]
        mid = np.hypot((yy - h / 2) / h, (xx - w / 2) / w) * 2 * CROP_HALF_KM * 1000 < 1700
        lon, lat = map(float, f[:-4].split("_")[:2])
        bbox = chips._bbox(lon, lat, CROP_HALF_KM)
        items = [i for start, end in EPOCHS for i in tried(chips.search, bbox, start, end, 40)]
        items = [i for i in items if str(i.datetime.date()) != str(z["day"])]
        best = (0.0, None, None)
        for item in items[:tries]:
            try:
                scl = np.array(Image.fromarray(chips._read(item.assets["scl"].href, bbox)[0]).resize((w, h), Image.NEAREST))
                cand = np.moveaxis(chips._read(item.assets["visual"].href, bbox), 0, -1)
            except Exception as e:  # noqa: BLE001  a broken or slow file: try the next day
                print("   skip", type(e).__name__, flush=True)
                continue
            if cand.shape[:2] != (h, w):
                cand = np.array(Image.fromarray(cand).resize((w, h), Image.BILINEAR))
            ok = ~np.isin(scl, chips.CLOUDY_SCL) & (scl != 0) & ~cloud_mask(cand) & (cand.sum(axis=2) > 0)
            cover = (ok & mid).sum() / mid.sum()
            if cover > best[0]:
                best = (cover, item, (cand, ok))
            if cover >= 0.995:
                break
        cover, item, got = best
        if item is None or cover < 0.97:
            print(slug, f, f"no clear day (best {cover * 100:.1f}%)", flush=True)
            continue
        cand, ok = got
        a = np.clip(gaussian_filter(mid.astype(float), 6), 0, 1) * ok   # feathered middle, clear pixels only
        rgb = (cand * a[..., None] + rgb * (1 - a[..., None])).astype(np.uint8)
        day = str(item.datetime.date())
        used = [x for x in z.get("filled", np.array([])).tolist() if x != "none"]
        np.savez_compressed(f"{d}/{f}", rgb=rgb, day=day, filled=np.array(used or ["none"]), swapped=np.array(day))
        print(slug, f, f"swapped to {day}, clear over {cover * 100:.1f}% of the middle", flush=True)


def pick(lon, lat, start, end, prev_day):
    """The clearest usable crop, but the previous piece's day first: one satellite pass covers a long way, so
    keeping its day keeps the light and colour the same and leaves no seam."""
    bbox = chips._bbox(lon, lat, CROP_HALF_KM)
    items = chips.search(bbox, start, end, 40)
    items = [i for i in items if str(i.datetime.date()) == prev_day] + [i for i in items if str(i.datetime.date()) != prev_day]
    for item in items[:12]:
        rgb = chips.scene(item, bbox)
        if rgb is not None:
            return item.datetime.date(), rgb
    return None


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
            prev = next((d for d in reversed(dates) if d), None)
            for start, end in EPOCHS:
                shot = tried(pick, mid.x, mid.y, start, end, prev)
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


def markers(slug, line, reaches, river):
    out = {"towns": [], "joins": [], "plants": [], "places": []}
    s = gpd.read_file("pipeline/out/cache/places/settlements_ghana.geojson").to_crs(CRS)
    # villages in or near the band; towns up to 5 km away (shown at the picture's edge with their distance)
    dist = s.distance(line)
    s = s[s["name"].notna() & (((s.place == "village") & (dist < 1500)) | (s.place.isin(["city", "town"]) & (dist < 5000)))]
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
            near = named[(named.distance(r.loc[k].geometry) < 1500) & ~named["name"].str.contains("|".join([RIVER[slug][0]] + ALIASES.get(RIVER[slug][0], [])), case=False)]
            nm = near["name"].mode().iloc[0] if len(near) else None
        end = Point(r.loc[k].geometry.coords[-1])
        up = geom.interpolate(max(geom.length * 0.5, geom.length - 1500)) if geom.geom_type == "LineString" else end   # 1.5 km up the branch
        walked = next((sl for sl, v in RIVER.items() if v[0] == nm), None)
        out["joins"].append({"name": nm, "slug": walked, "km": round(line.project(end) / 1000, 2),
                             "side": "left" if offset(line, up) > 0 else "right", "upland_km2": round(float(r.loc[k].UPLAND_SKM))})
    plants = gpd.read_file("pipeline/water_plants.geojson").to_crs(CRS)
    pts = gpd.GeoSeries(gpd.points_from_xy(plants.plant_lon, plants.plant_lat), crs=4326).to_crs(CRS)
    for (_, p), pt in zip(plants.iterrows(), pts):
        if pt.distance(river) < 1500:
            out["plants"].append({"name": p["plant"], "km": round(line.project(pt) / 1000, 2)})
    pl = gpd.read_file("pipeline/out/places/latest.geojson").to_crs(CRS)
    idx = json.load(open("pipeline/out/places/index.json", encoding="utf-8"))
    pl = pl[pl.distance(river) < HALF_M]   # within 1 km of the water itself
    for _, p in pl.iterrows():
        c = p.geometry.representative_point()
        i = idx.get(p["id"], {})
        out["places"].append({"id": p["id"], "km": round(line.project(c) / 1000, 3), "off_m": round(offset(line, c)),
                              "river_m": round(p.geometry.distance(river)),
                              "ha": i.get("ha"), "licence": i.get("licence"), "likely": bool(i.get("likely_galamsey")),
                              "near": i.get("near"), "near_km": i.get("near_km")})
    for k in out:
        out[k].sort(key=lambda m: m["km"])
    # where the course leaves the forest zone for good (clearing is not counted below it)
    from tracker import zone
    z = gpd.GeoSeries([zone.load()], crs=4326).to_crs(CRS).iloc[0]
    inside = [z.contains(line.interpolate(d)) for d in np.arange(0, line.length, 500)]
    if inside and not inside[-1] and any(inside):
        last = max(i for i, v in enumerate(inside) if v)
        out["zone_end_km"] = round((last + 1) * 0.5, 1)
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
    river, reaches, streams_km = course(slug)
    gpd.GeoSeries([river], crs=CRS).to_crs(4326).to_file(f"{out}/course.geojson")
    line, along = guide(river)
    print(f"picture sideways jumps: {jumps(line)}", flush=True)
    m = markers(slug, line, reaches, river)
    simple = gpd.GeoSeries([river.simplify(200)], crs=CRS).to_crs(4326).iloc[0]
    # river km still to go, at every 0.5 km down the picture (the picture is shorter: bends are not pulled out)
    gxy = np.array(line.coords)
    cum = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(gxy, axis=0), axis=1))])
    left = river.length - np.interp(np.arange(0, line.length, 500), cum, along)
    meta = {"slug": slug, "name": RIVER[slug][0], "ends": RIVER[slug][2], "length_km": round(line.length / 1000, 1),
            "river_km": round(river.length / 1000, 1), "km_left": [round(v / 1000, 2) for v in left] + [0.0], "streams_km": round(streams_km),
            "step_m": STEP_M, "half_m": HALF_M, "tile_km": TILE_KM, "course": [[round(x, 4), round(y, 4)] for x, y in simple.coords],
            **m}
    json.dump(meta, open(f"{out}/river.json", "w", encoding="utf-8"), indent=1)
    print({k: (len(v) if isinstance(v, list) else v) for k, v in m.items()}, flush=True)
    if only_course:
        return
    img, dates = picture(slug, line)
    meta["dates"] = sorted({d for d in dates if d})
    # days used to fill cloudy spots (fill step), so the page can say where they come from
    fills = set()
    for f in os.listdir(_cache_dir(slug)):
        z = np.load(f"{_cache_dir(slug)}/{f}")
        if "filled" in z:
            fills |= {str(v) for v in z["filled"] if str(v) != "none"}
    meta["fill_dates"] = sorted(fills)
    json.dump(meta, open(f"{out}/river.json", "w", encoding="utf-8"), indent=1)
    Image.fromarray(img).save(f"{out}/strip.png")
    rows = TILE_KM * 1000 // STEP_M
    for i, r0 in enumerate(range(0, img.shape[0], rows)):
        Image.fromarray(img[r0:r0 + rows]).save(f"{out}/tile-{i:03d}.webp", quality=82, method=6)


if __name__ == "__main__":
    if sys.argv[2:] == ["fill"]:
        fill(sys.argv[1])
    elif sys.argv[2:] == ["swap"]:
        swap(sys.argv[1])
    else:
        run(sys.argv[1], only_course=sys.argv[2:] == ["course"])
