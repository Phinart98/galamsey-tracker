import geopandas as gpd
from shapely.geometry import box

from tracker.zone import inside

CRS = "EPSG:32630"


def test_patches_count_only_when_they_sit_in_the_forest_zone():
    zone = gpd.GeoSeries([box(0, 0, 1000, 1000)], crs=CRS).to_crs(4326).iloc[0]
    patches = gpd.GeoDataFrame({"ha": [5.0, 3.0, 2.0]}, crs=CRS, geometry=[
        box(100, 100, 300, 300),      # inside
        box(5000, 5000, 5200, 5200),  # outside
        box(900, 100, 1400, 300),     # straddles the edge, more than half outside
    ])
    assert inside(patches, zone).ha.tolist() == [5.0]
