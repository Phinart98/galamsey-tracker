"""Readable place names: nearest known town (or village) and district.

Districts: geoBoundaries GHA ADM2 (260 districts, 2019, Ghana Statistical Service, CC BY 4.0).
Settlements: OpenStreetMap place=city|town|village with a name (ODbL), via Geofabrik's Ghana extract.
"""
import os
import time

import geopandas as gpd
import pandas as pd
import requests

from tracker.config import HEADERS
from tracker.licences import NO_LICENCE_TO_MINE

ADM2 = ("https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/GHA/ADM2/"
        "geoBoundaries-GHA-ADM2_simplified.geojson")
GHANA_OSM = "https://download.geofabrik.de/africa/ghana-latest.osm.pbf"
TOWN_M = 15000    # readers recognise towns from further away than villages
VILLAGE_M = 8000  # beyond this, "near X" stops helping and the district alone is clearer
SAME_PLACE_M = 2000  # two OSM points with one name this close are one village mapped twice
NEAR_M = 1000     # "on the doorstep": cleared land this close to a town or village (spike log s19)
NAMES_MAX_AGE_DAYS = 90  # OpenStreetMap names improve over time, so the saved list is refreshed every three months


def _cached(path: str, fetch, max_age_days: int | None = None) -> str:
    """Download once and keep the copy. With max_age_days, download again once it is older, keeping the old
    copy if that fails (the run goes on with slightly older names rather than stopping)."""
    stale = max_age_days is not None and os.path.exists(path) and time.time() - os.path.getmtime(path) > max_age_days * 86400
    if not os.path.exists(path) or stale:
        try:
            data = fetch()
        except (OSError, ValueError) as e:
            if not stale:
                raise
            print(f"places: could not refresh {os.path.basename(path)} ({type(e).__name__}), keeping the saved copy")
            return path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
    return path


def districts(cache_dir: str) -> gpd.GeoDataFrame:
    def fetch():
        r = requests.get(ADM2, timeout=120)
        r.raise_for_status()
        return r.content
    gdf = gpd.read_file(_cached(os.path.join(cache_dir, "districts.geojson"), fetch))
    return gdf[["shapeName", "geometry"]].rename(columns={"shapeName": "district"})


def _read_osm_places(pbf: str) -> gpd.GeoDataFrame:
    g = gpd.read_file(pbf, layer="points", where="place IN ('city','town','village') AND name IS NOT NULL",
                      columns=["name", "place"])
    return g[["name", "place", "geometry"]]


def _download(url: str, path: str):
    with requests.get(url, headers=HEADERS, timeout=600, stream=True) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            f.writelines(r.iter_content(1 << 20))


def settlements(cache_dir: str) -> gpd.GeoDataFrame:
    """Every named city, town and village in Ghana, so any tile switched on later already has its names.

    From Geofabrik's daily Ghana extract: the Overpass API returned 502 and its mirrors timed out (2026-10-25),
    and a cache made for one tile's area once left five newer tiles without town names.
    """
    def fetch():
        pbf = os.path.join(cache_dir, "ghana.osm.pbf")
        _download(GHANA_OSM, pbf)
        try:
            return _read_osm_places(pbf).to_json().encode()
        finally:
            os.remove(pbf)
    return gpd.read_file(_cached(os.path.join(cache_dir, "settlements_ghana.geojson"), fetch, NAMES_MAX_AGE_DAYS))


def name(clusters: gpd.GeoDataFrame, towns_and_villages: gpd.GeoDataFrame, district_polys: gpd.GeoDataFrame):
    """Return (near, near_km, district) series aligned with clusters."""
    pts = gpd.GeoDataFrame(geometry=clusters.geometry.representative_point(), crs=clusters.crs)
    places = towns_and_villages.to_crs(clusters.crs)

    def nearest(subset, max_m):
        j = gpd.sjoin_nearest(pts, subset[["name", "geometry"]], how="left", max_distance=max_m, distance_col="m")
        return j[~j.index.duplicated()]

    towns = nearest(places[places.place.isin(["city", "town"])], TOWN_M)
    villages = nearest(places[places.place == "village"], VILLAGE_M)
    near = towns.where(towns["name"].notna(), villages)
    dist = gpd.sjoin(pts, district_polys.to_crs(clusters.crs), how="left", predicate="within")
    dist = dist[~dist.index.duplicated()]
    return near["name"], (near["m"] / 1000).round(1), dist["district"]


def _one_per_place(t: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Drop a settlement that has a namesake already listed within SAME_PLACE_M: OSM maps some villages twice."""
    pairs = gpd.sjoin(t[["name", "geometry"]], gpd.GeoDataFrame(t[["name"]], geometry=t.buffer(SAME_PLACE_M)),
                      predicate="within")
    dupes = pairs[(pairs.name_left == pairs.name_right) & (pairs.index_right < pairs.index)].index
    return t.drop(index=dupes.unique())


def towns_near(clusters: gpd.GeoDataFrame, towns_and_villages: gpd.GeoDataFrame, district_polys: gpd.GeoDataFrame,
               radius_m: int = NEAR_M) -> pd.DataFrame:
    """Every town and village with cleared land within radius_m, most cleared land first.

    Rows keep their own district, so two villages with the same name stay apart. ids lists the patches
    largest first. ha counts only the part of each patch inside the ring, so "within 1 km" stays true.
    OpenStreetMap misses many villages in rural Ghana, so the count is a floor.
    """
    t = _one_per_place(towns_and_villages.to_crs(clusters.crs).reset_index(drop=True))
    ring = gpd.GeoDataFrame(geometry=t.buffer(radius_m), crs=clusters.crs)
    cols = ["id", "ha", "licence", "geometry"] if "licence" in clusters else ["id", "ha", "geometry"]
    hits = gpd.sjoin(clusters[cols], ring, predicate="intersects").sort_values("ha", ascending=False)
    rings = gpd.GeoSeries(ring.geometry.loc[hits.index_right].values, index=hits.index, crs=clusters.crs)
    inside = hits.geometry.intersection(rings).area
    share = (inside / hits.geometry.area).clip(upper=1).where(~hits.geometry.within(rings), 1.0)  # wholly inside: all of it
    hits["inside_ha"] = hits.ha * share
    hits["no_licence_ha"] = hits.inside_ha.where(hits.licence.isin(NO_LICENCE_TO_MINE), 0.0) if "licence" in hits else 0.0
    per = hits.groupby("index_right").agg(ha=("inside_ha", "sum"), no_licence_ha=("no_licence_ha", "sum"),
                                          patches=("id", "size"), ids=("id", list))
    dist = gpd.sjoin_nearest(t[["geometry"]], district_polys.to_crs(clusters.crs)[["district", "geometry"]], how="left")
    ll = t.geometry.to_crs(4326)
    out = per.join(pd.DataFrame({"name": t.name, "place": t.place, "district": dist[~dist.index.duplicated()].district,
                                 "lat": ll.y, "lon": ll.x}))
    return out.sort_values("ha", ascending=False, kind="stable").reset_index(drop=True)[
        ["name", "place", "district", "lat", "lon", "ha", "no_licence_ha", "patches", "ids"]]
