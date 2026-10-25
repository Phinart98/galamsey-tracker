"""The forest zone of southern Ghana: only clearing inside it is counted.

Galamsey works the gold belts in the forest zone. North of it (the Afram Plains, northern Kwahu) and on the coastal
savanna, a by-eye check found clearing was almost all farm and fire clearing, a falling lake shore and building
sites (spike log s20). The zone is the "Eastern Guinean forests" ecoregion from RESOLVE Ecoregions 2017
(Dinerstein et al. 2017, CC BY 4.0), made by spike/forest_zone.py.
"""
import os

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "forest_zone.geojson")


def load() -> BaseGeometry:
    return gpd.read_file(PATH).union_all()


def inside(patches: gpd.GeoDataFrame, zone: BaseGeometry) -> gpd.GeoDataFrame:
    """Patches whose representative point lies in the zone, in lon/lat zone coordinates."""
    pts = patches.geometry.representative_point().to_crs(4326)
    return patches[pts.within(zone).values]
