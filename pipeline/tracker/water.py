"""Cleared land upstream of the treatment plants that supply cities with water.

The catchments are every HydroBASINS level 12 basin (Lehner and Grill 2013) upstream of each plant, made by
spike/water_plants.py (spike log s16, s23). Clearing upstream is not a measure of what reaches the plant.
"""
import os

import geopandas as gpd

from tracker.licences import NO_LICENCE_TO_MINE

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "water_plants.geojson")


def load() -> gpd.GeoDataFrame:
    return gpd.read_file(PATH)


def upstream(clusters: gpd.GeoDataFrame, plants: gpd.GeoDataFrame) -> list[dict]:
    """Hectares of patches whose representative point lies in each plant's catchment, in plant order: all of
    them (the site), and those with no licence to mine (the studio's posts, which show only that land)."""
    licensed = "licence" in clusters  # missing only in tests that need the totals alone
    pts = gpd.GeoDataFrame(clusters[["ha", "licence"] if licensed else ["ha"]], geometry=clusters.geometry.representative_point(), crs=clusters.crs)
    p = plants.to_crs(clusters.crs).reset_index(drop=True)
    hit = gpd.sjoin(pts, p[["geometry"]], predicate="within")
    ha = hit.groupby("index_right").ha.sum()
    out = [{"plant": r.plant, "river": r.river, "ha": round(float(ha.get(i, 0.0)), 1)} for i, r in p.iterrows()]
    if licensed:
        nl = hit[hit.licence.isin(NO_LICENCE_TO_MINE)].groupby("index_right").ha.sum()
        for i, row in enumerate(out):
            row["no_licence_ha"] = round(float(nl.get(i, 0.0)), 1)
    return out
