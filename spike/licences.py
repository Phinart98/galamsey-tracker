"""Minerals Commission active licences: snapshot, repair, and classify clusters.

The cadastre portal (ghana.revenuedev.org) loads its map from a public GeoJSON
endpoint. Reuse terms are not published, so v1 only uses it to classify
clusters by licence *type*, never to redistribute boundaries or name holders.
"""
import datetime as dt
import json
import os
import sys

import geopandas as gpd
import requests
from shapely.geometry import shape
from shapely.validation import make_valid

URL = ("https://repo-prod.revenuedev.org/api/map/geojson/GH/ws/-1"
       "?status=Active%20Licenses&type=&owner.id=&minerals.id=")
HEADERS = {"User-Agent": "galamsey-tracker/0.1 (+https://github.com/Phinart98/galamsey-tracker)"}

NONE, PROSPECTING, SMALL_SCALE, LARGE_SCALE = "no licence", "prospecting only", "small-scale licence", "large-scale lease"
# Ties between equal shares go to the more permissive licence, the fairest reading for its holder.
RANK = {NONE: 0, PROSPECTING: 1, SMALL_SCALE: 2, LARGE_SCALE: 3}
# Restricted leases cover granite, sand, gravel, limestone, salt and clay: none is a right to dig for gold.
INDUSTRIAL = {"granite", "sand", "sand/ gravel", "gravel", "limestone", "salt", "clay", "feldspar", "kaolin"}


def licence_class(licence_type: str, minerals: list[str]) -> str | None:
    """Class of a licence for gold-type mining, or None when it does not cover such mining."""
    names = {m.strip().lower() for m in minerals}
    if names and names <= INDUSTRIAL:
        return None
    t = licence_type.lower()
    if "restricted" in t and not names:
        return None
    if "prospecting" in t or "reconnaissance" in t:
        return PROSPECTING
    if "small scale" in t:
        return SMALL_SCALE
    if "mining lease" in t:
        return LARGE_SCALE
    return None


def fetch_snapshot(out_dir="data/licences"):
    os.makedirs(out_dir, exist_ok=True)
    path = f"{out_dir}/{dt.date.today()}.geojson"
    if not os.path.exists(path):
        r = requests.get(URL, headers=HEADERS, timeout=120)
        r.raise_for_status()
        with open(path, "w", encoding="utf-8") as f:
            f.write(r.text)
    return path


def load_licences(path):
    rows, bad = [], 0
    for f in json.load(open(path, encoding="utf-8"))["features"]:
        try:
            geom = make_valid(shape(f["geometry"]))
        except (ValueError, TypeError, KeyError):
            bad += 1
            continue
        minerals = [a.get("name", "") for a in (f["properties"].get("assets") or [])]
        cls = licence_class(f["properties"].get("type") or "", minerals)
        if cls:
            rows.append({"type": f["properties"]["type"], "cls": cls, "geometry": geom})
    return gpd.GeoDataFrame(rows, crs=4326), bad


def classify(clusters: gpd.GeoDataFrame, licences: gpd.GeoDataFrame, min_share=0.25):
    """Licence class per cluster: the class covering the largest share of its area, if at least min_share."""
    lic = licences.to_crs(clusters.crs)
    inter = gpd.overlay(clusters[["id", "geometry"]], lic[["cls", "geometry"]], how="intersection", keep_geom_type=True)
    inter["share"] = inter.area / inter["id"].map(clusters.set_index("id").area)
    share = inter.groupby(["id", "cls"]).share.sum().clip(upper=1).reset_index()
    share = share[share.share >= min_share]
    best = (share.assign(rank=share.cls.map(RANK)).sort_values(["share", "rank"])
            .groupby("id").tail(1).set_index("id"))
    return clusters["id"].map(best.cls).fillna(NONE)


if __name__ == "__main__":
    clusters = gpd.read_file(sys.argv[1] if len(sys.argv) > 1 else "data/clusters_30NXM.gpkg")
    licences, bad = load_licences(fetch_snapshot())
    print(f"licences used {len(licences)}, unparseable {bad}")
    clusters["licence"] = classify(clusters, licences)
    print(clusters.head(5)[["id", "ha", "licence"]].to_string(index=False))
    t = clusters.groupby("licence").ha.agg(["count", "sum"])
    t["share"] = (t["sum"] / t["sum"].sum() * 100).round(0)
    print(t.round(0).to_string())
    clusters.to_file("data/clusters_30NXM.gpkg")
