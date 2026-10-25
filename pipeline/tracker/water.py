"""Cleared land upstream of the treatment plants that supply cities with water.

The catchments are every HydroBASINS level 12 basin (Lehner and Grill 2013) upstream of each plant, made by
spike/water_plants.py (spike log s16, s23). Clearing upstream is not a measure of what reaches the plant.
"""
import os

import geopandas as gpd

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "water_plants.geojson")


def load() -> gpd.GeoDataFrame:
    return gpd.read_file(PATH)


def upstream(clusters: gpd.GeoDataFrame, plants: gpd.GeoDataFrame) -> list[dict]:
    """Hectares of patches whose representative point lies in each plant's catchment, in plant order."""
    pts = gpd.GeoDataFrame(clusters[["ha"]], geometry=clusters.geometry.representative_point(), crs=clusters.crs)
    p = plants.to_crs(clusters.crs).reset_index(drop=True)
    ha = gpd.sjoin(pts, p[["geometry"]], predicate="within").groupby("index_right").ha.sum()
    return [{"plant": r.plant, "river": r.river, "ha": round(float(ha.get(i, 0.0)), 1)} for i, r in p.iterrows()]
