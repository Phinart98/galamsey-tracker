"""The forest zone of southern Ghana, where the gold belts and galamsey are, as a small file for the pipeline.

From RESOLVE Ecoregions 2017 (Dinerstein et al. 2017, CC BY 4.0), the "Eastern Guinean forests" ecoregion
clipped to southern Ghana and simplified to about 100 m. Clearing outside it, in the forest-savanna mosaic and
coastal savanna, was mostly farm and fire clearing and building sites (spike log s20, s21).

Download https://storage.googleapis.com/teow2016/Ecoregions2017.zip to spike/data/eco/eco.zip, then run from
the repo root: uv run --project pipeline python spike/forest_zone.py
"""
import geopandas as gpd
from shapely.geometry import box

eco = gpd.read_file("zip://spike/data/eco/eco.zip", bbox=(-3.5, 4.5, 1.5, 8.5))
forest = eco[eco.ECO_NAME == "Eastern Guinean forests"].to_crs(32630).union_all().simplify(100)
ghana_south = gpd.GeoSeries([box(-3.5, 4.5, 1.5, 8.5)], crs=4326).to_crs(32630).iloc[0]
zone = gpd.GeoDataFrame({"name": ["Eastern Guinean forests (RESOLVE Ecoregions 2017, CC BY 4.0)"]},
                        geometry=[forest.intersection(ghana_south)], crs=32630).to_crs(4326)
zone.to_file("pipeline/forest_zone.geojson", driver="GeoJSON", COORDINATE_PRECISION=4)
print("written", zone.geometry.iloc[0].geom_type, round(zone.to_crs(32630).area.iloc[0] / 1e6), "km2")
