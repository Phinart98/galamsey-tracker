"""Readable place names: nearest known town (or village) and district.

Districts: geoBoundaries GHA ADM2 (260 districts, 2019, Ghana Statistical Service, CC BY 4.0).
Settlements: OpenStreetMap place=city|town|village with a name (ODbL).
"""
import os

import geopandas as gpd
import requests

ADM2 = ("https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/GHA/ADM2/"
        "geoBoundaries-GHA-ADM2_simplified.geojson")
OVERPASS = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "galamsey-tracker/0.1 (+https://github.com/Phinart98/galamsey-tracker)"}
TOWN_M = 15000    # readers recognise towns from further away than villages
VILLAGE_M = 8000  # beyond this, "near X" stops helping and the district alone is clearer


def _cached(path: str, fetch) -> str:
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(fetch())
    return path


def districts(cache_dir: str) -> gpd.GeoDataFrame:
    def fetch():
        r = requests.get(ADM2, timeout=120)
        r.raise_for_status()
        return r.content
    gdf = gpd.read_file(_cached(os.path.join(cache_dir, "districts.geojson"), fetch))
    return gdf[["shapeName", "geometry"]].rename(columns={"shapeName": "district"})


def settlements(cache_dir: str, bbox: tuple[float, float, float, float]) -> gpd.GeoDataFrame:
    west, south, east, north = bbox

    def fetch():
        q = (f'[out:json][timeout:180];node["place"~"^(city|town|village)$"]["name"]'
             f'({south},{west},{north},{east});out;')
        r = requests.post(OVERPASS, data={"data": q}, headers=HEADERS, timeout=240)
        r.raise_for_status()
        rows = [{"name": e["tags"]["name"], "place": e["tags"]["place"], "lon": e["lon"], "lat": e["lat"]}
                for e in r.json()["elements"]]
        g = gpd.GeoDataFrame(rows, geometry=gpd.points_from_xy([r["lon"] for r in rows], [r["lat"] for r in rows]),
                             crs=4326)
        return g.to_json().encode()
    return gpd.read_file(_cached(os.path.join(cache_dir, "settlements.geojson"), fetch))


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
