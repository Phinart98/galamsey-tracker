"""Minerals Commission active licences: fetch, repair, and classify cleared patches by licence.

The cadastre portal (ghana.revenuedev.org) loads its map from a public GeoJSON endpoint.
Reuse terms are not published, so we only classify patches by licence *type*. Boundaries
are never redistributed and holders are never named.
"""
import json

import geopandas as gpd
import requests
from shapely.geometry import shape
from shapely.validation import make_valid

from tracker.config import HEADERS

URL = ("https://repo-prod.revenuedev.org/api/map/geojson/GH/ws/-1"
       "?status=Active%20Licenses&type=&owner.id=&minerals.id=")

NONE = "no licence"
PROSPECTING = "prospecting only"
SMALL_SCALE = "small-scale licence"
LARGE_SCALE = "large-scale lease"
# Restricted leases are for industrial minerals (Act 703): in the register granite, sand, gravel, limestone, clay
# and salt. They allow quarrying, not gold mining, so they get their own label rather than "no licence".
RESTRICTED = "restricted lease"
# Equal shares go to the more permissive licence: the fairest reading for whoever holds it.
RANK = {PROSPECTING: 1, RESTRICTED: 2, SMALL_SCALE: 3, LARGE_SCALE: 4}
MIN_SHARE = 0.25
NO_LICENCE_TO_MINE = (NONE, PROSPECTING)  # no licence at all, or only one to explore: mining here is galamsey
# The register held 1,058 usable licences in November 2026. Far fewer means the download came back incomplete,
# and classifying with it would label licensed mines "no licence", so the run stops instead.
MIN_USABLE = 800


def licence_class(licence_type: str) -> str | None:
    t = licence_type.lower()
    if "restricted" in t:
        return RESTRICTED
    if "prospecting" in t or "reconnaissance" in t:
        return PROSPECTING
    if "small scale" in t:
        return SMALL_SCALE
    if "mining lease" in t:
        return LARGE_SCALE
    return None


def fetch(timeout=120) -> dict:
    r = requests.get(URL, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()


def parse(geojson: dict) -> tuple[gpd.GeoDataFrame, int]:
    """Licences that allow some gold-type activity, plus a count of geometries we could not repair."""
    rows, bad = [], 0
    for f in geojson["features"]:
        try:
            geom = make_valid(shape(f["geometry"]))
        except (ValueError, TypeError, KeyError, AttributeError):  # AttributeError: a null geometry
            bad += 1
            continue
        props = f.get("properties") or {}
        cls = licence_class(props.get("type") or "")
        if cls:
            rows.append({"cls": cls, "geometry": geom})
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=4326), bad


def check(licences: gpd.GeoDataFrame):
    if len(licences) < MIN_USABLE:
        raise RuntimeError(f"the licence register gave only {len(licences)} usable licences (expected {MIN_USABLE}+)")


def classify(clusters: gpd.GeoDataFrame, licences: gpd.GeoDataFrame, min_share=MIN_SHARE):
    """For each cluster, the licence class covering the largest share of its area (at least min_share)."""
    by_class = licences.to_crs(clusters.crs).dissolve(by="cls").reset_index()[["cls", "geometry"]]
    area = clusters.geometry.area
    best_cls = [NONE] * len(clusters)
    best_key = [(0.0, 0)] * len(clusters)
    for _, lic in by_class.iterrows():
        share = clusters.geometry.intersection(lic.geometry).area / area
        for i, s in enumerate(share):
            key = (round(float(s), 6), RANK[lic.cls])
            if s >= min_share and key > best_key[i]:
                best_key[i], best_cls[i] = key, lic.cls
    return gpd.pd.Series(best_cls, index=clusters.index)


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
