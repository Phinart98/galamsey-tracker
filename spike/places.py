"""Name each cluster by its nearest settlement and its district, for readers who don't think in coordinates.

Districts: geoBoundaries GHA ADM2 (260 districts, 2019, Ghana Statistical Service, CC BY 4.0).
Settlements: OpenStreetMap place=city|town|village with a name (ODbL).
"""
import json
import os

import geopandas as gpd
import requests

ADM2 = ("https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/GHA/ADM2/"
        "geoBoundaries-GHA-ADM2_simplified.geojson")
OVERPASS = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "galamsey-tracker/0.1 (+https://github.com/Phinart98/galamsey-tracker)"}
TOWN_M = 15000    # readers recognise towns from further away than villages
VILLAGE_M = 8000  # beyond this, "near X" stops being useful and we name the district only


def districts(path="data/places/districts.geojson"):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        r = requests.get(ADM2, timeout=120)
        r.raise_for_status()
        open(path, "wb").write(r.content)
    return gpd.read_file(path)[["shapeName", "geometry"]].rename(columns={"shapeName": "district"})


def settlements(bbox, path="data/places/settlements.geojson"):
    if not os.path.exists(path):
        south, west, north, east = bbox[1], bbox[0], bbox[3], bbox[2]
        q = f'[out:json][timeout:120];node["place"~"^(city|town|village)$"]["name"]({south},{west},{north},{east});out;'
        r = requests.post(OVERPASS, data={"data": q}, headers=HEADERS, timeout=180)
        r.raise_for_status()
        feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [e["lon"], e["lat"]]},
                  "properties": {"name": e["tags"]["name"], "place": e["tags"]["place"]}}
                 for e in r.json()["elements"]]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump({"type": "FeatureCollection", "features": feats}, open(path, "w", encoding="utf-8"))
    return gpd.read_file(path)


def name_places(clusters: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    pts = clusters.copy()
    pts["geometry"] = clusters.representative_point()
    bbox = list(pts.to_crs(4326).total_bounds + [-0.1, -0.1, 0.1, 0.1])
    places = settlements(bbox).to_crs(clusters.crs)

    def nearest(subset, max_m):
        j = gpd.sjoin_nearest(pts[["id", "geometry"]], subset[["name", "geometry"]], how="left",
                              max_distance=max_m, distance_col="near_m")
        return j[~j.index.duplicated()]

    towns = nearest(places[places.place.isin(["city", "town"])], TOWN_M)
    villages = nearest(places[places.place == "village"], VILLAGE_M)
    near = towns.where(towns["name"].notna(), villages)
    dist = gpd.sjoin(pts[["id", "geometry"]], districts().to_crs(clusters.crs), how="left", predicate="within")
    dist = dist[~dist.index.duplicated()]
    out = clusters.copy()
    out["near"] = near["name"]
    out["near_km"] = (near["near_m"] / 1000).round(1)
    out["district"] = dist["district"]
    return out


if __name__ == "__main__":
    import warnings; warnings.filterwarnings("ignore")
    c = gpd.read_file("data/clusters_30NXM.gpkg")
    named = name_places(c)
    named[["id", "near", "near_km", "district"]].to_csv("data/places_30NXM.csv", index=False)
    print(named.head(8)[["id", "ha", "near", "near_km", "district"]].to_string(index=False))
    print("unnamed (no town within 15 km or village within 8 km):", named.near.isna().sum(), "| no district:", named.district.isna().sum())
