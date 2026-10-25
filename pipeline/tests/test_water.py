import geopandas as gpd
from shapely.geometry import Point, box

from tracker import water

CRS = "EPSG:32630"


def test_clearing_upstream_of_each_plant_counts_patches_whose_centre_is_in_its_catchment():
    plants = gpd.GeoDataFrame({"plant": ["Daboase", "Weija"], "river": ["Pra", "Densu"]}, crs=CRS,
                              geometry=[box(0, 0, 10000, 10000), box(20000, 0, 30000, 10000)]).to_crs(4326)
    clusters = gpd.GeoDataFrame({"ha": [5.0, 7.0, 1.0]}, crs=CRS, geometry=[
        Point(1000, 1000).buffer(100), Point(9990, 5000).buffer(100), Point(50000, 0).buffer(100)])
    assert water.upstream(clusters, plants) == [
        {"plant": "Daboase", "river": "Pra", "ha": 12.0}, {"plant": "Weija", "river": "Densu", "ha": 0.0}]
