"""Stable identities for cleared patches, so a shared /places/<id> link keeps pointing at the same place.

A patch keeps its id while its seed point (where it was first seen) stays inside it. When patches
merge, the oldest id wins and the others become aliases that the site redirects.
"""
from collections.abc import Callable

import geopandas as gpd
import pandas as pd

DUPLICATE_SHARE = 0.5  # MGRS tiles overlap by ~10 km, so the same patch can arrive from two tiles


def make_id(lon: float, lat: float, first_seen: str) -> str:
    ns = "n" if lat >= 0 else "s"
    ew = "w" if lon < 0 else "e"
    return f"{first_seen[:7]}-{round(abs(lat) * 1000):04d}{ns}{round(abs(lon) * 1000):04d}{ew}"


def dedupe_tiles(per_tile: list[gpd.GeoDataFrame]) -> gpd.GeoDataFrame:
    frames = [f for f in per_tile if len(f)]
    if not frames:
        return per_tile[0] if per_tile else gpd.GeoDataFrame(geometry=[])
    crs = frames[0].crs
    allc = pd.concat([f.to_crs(crs) for f in frames], ignore_index=True)
    allc = gpd.GeoDataFrame(allc, geometry="geometry", crs=crs).sort_values("ha", ascending=False, kind="stable")
    allc = allc.reset_index(drop=True)
    geoms, tiles = allc.geometry.values, allc["tile"].values
    # Only patches whose boxes touch can be duplicates. Comparing every pair took ~10 minutes for six tiles.
    left, right = allc.sindex.query(allc.geometry, predicate="intersects")
    touching: dict[int, list[int]] = {}
    for i, j in zip(left, right):
        if j < i and tiles[i] != tiles[j]:
            touching.setdefault(i, []).append(j)
    kept = set()
    for i in range(len(allc)):
        g = geoms[i]
        if not any(j in kept and g.intersection(geoms[j]).area >= DUPLICATE_SHARE * g.area for j in touching.get(i, ())):
            kept.add(i)
    return allc.loc[sorted(kept)].reset_index(drop=True)


def resolve_aliases(aliases: dict[str, str], active: set[str]) -> dict[str, str]:
    """Aliases the site can redirect: each points at the end of its chain of merges, and an old id that is a
    place of its own again (active) is dropped. A chain that loops or ends at an inactive place is dropped too."""
    out = {}
    for old, to in aliases.items():
        if old in active:
            continue
        seen = {old}
        while to in aliases and to not in active and to not in seen:
            seen.add(to)
            to = aliases[to]
        if to in active:
            out[old] = to
    return out


def match_ids(new: gpd.GeoDataFrame, previous: gpd.GeoDataFrame | None,
              to_lonlat: Callable[[float, float], tuple[float, float]]) -> tuple[gpd.GeoDataFrame, dict[str, str]]:
    """Assign ids and seed points to new patches; return them plus {old_id: surviving_id} aliases."""
    out = new.copy()
    ids, seeds, aliases, used = [], [], {}, set()
    seeds_prev = previous.to_crs(new.crs) if previous is not None and len(previous) else None
    # Old ids stay reserved, so a new patch never takes over an old place's page and pictures
    taken = set(seeds_prev.id) if seeds_prev is not None else set()
    # Which old seeds lie in which new patch, found once with a spatial index (a pair-by-pair test grew to
    # tens of millions of checks a week as seeds pile up)
    holds: dict[int, list[int]] = {}
    if seeds_prev is not None:
        for patch, seed in zip(*seeds_prev.sindex.query(new.geometry, predicate="contains")):
            holds.setdefault(int(patch), []).append(int(seed))
    for pos, (_, row) in enumerate(new.iterrows()):
        inside = seeds_prev.iloc[sorted(holds.get(pos, []))] if seeds_prev is not None else None
        # One old seed can sit inside two patches (tile copies that overlap by less than half).
        # The first, larger patch keeps the id and the other becomes a new place.
        if inside is not None:
            inside = inside[~inside.id.isin(used)]
        if inside is not None and len(inside):
            inside = inside.sort_values(["first_seen", "id"])
            winner = inside.iloc[0]
            ids.append(winner.id)
            seeds.append(winner.geometry)
            for loser in inside.iloc[1:].id:
                aliases[loser] = winner.id
        else:
            seed = row.geometry.representative_point()
            lon, lat = to_lonlat(seed.x, seed.y)
            base = candidate = make_id(lon, lat, row.first_seen)
            n = 2
            while candidate in used or candidate in taken:
                candidate, n = f"{base}-{n}", n + 1
            ids.append(candidate)
            seeds.append(seed)
        used.add(ids[-1])
    out["id"] = ids
    out["seed"] = gpd.GeoSeries(seeds, crs=new.crs, index=new.index)
    return out, aliases
