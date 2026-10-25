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
    kept = []
    for idx, row in allc.iterrows():
        dup = any(other.tile != row.tile
                  and row.geometry.intersection(other.geometry).area >= DUPLICATE_SHARE * row.geometry.area
                  for other in kept)
        if not dup:
            kept.append(row)
    return gpd.GeoDataFrame(kept, geometry="geometry", crs=crs).reset_index(drop=True)


def match_ids(new: gpd.GeoDataFrame, previous: gpd.GeoDataFrame | None,
              to_lonlat: Callable[[float, float], tuple[float, float]]) -> tuple[gpd.GeoDataFrame, dict[str, str]]:
    """Assign ids and seed points to new patches; return them plus {old_id: surviving_id} aliases."""
    out = new.copy()
    ids, seeds, aliases, used = [], [], {}, set()
    seeds_prev = previous.to_crs(new.crs) if previous is not None and len(previous) else None
    for _, row in new.iterrows():
        inside = seeds_prev[seeds_prev.within(row.geometry)] if seeds_prev is not None else None
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
            while candidate in used:
                candidate, n = f"{base}-{n}", n + 1
            ids.append(candidate)
            seeds.append(seed)
        used.add(ids[-1])
    out["id"] = ids
    out["seed"] = gpd.GeoSeries(seeds, crs=new.crs, index=new.index)
    return out, aliases
