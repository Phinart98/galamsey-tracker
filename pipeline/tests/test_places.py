import geopandas as gpd
from shapely.geometry import Point

from tracker import places


def test_towns_for_all_of_ghana_are_downloaded_once_and_then_read_from_the_cache(monkeypatch, tmp_path):
    downloads = []

    def download(url, path):
        downloads.append(url)
        open(path, "wb").close()

    towns = gpd.GeoDataFrame({"name": ["Dunkwa", "Bolgatanga"], "place": ["town", "town"]},
                             geometry=[Point(-1.78, 5.96), Point(-0.85, 10.79)], crs=4326)
    monkeypatch.setattr(places, "_download", download)
    monkeypatch.setattr(places, "_read_osm_places", lambda pbf: towns)
    first = places.settlements(str(tmp_path))
    again = places.settlements(str(tmp_path))
    assert sorted(first.name) == sorted(again.name) == ["Bolgatanga", "Dunkwa"]
    assert len(downloads) == 1
    assert not (tmp_path / "ghana.osm.pbf").exists()  # the 100 MB extract is not kept


def test_towns_near_count_clearing_within_a_kilometre_and_keep_same_named_villages_apart():
    crs = "EPSG:32630"
    towns = gpd.GeoDataFrame({"name": ["Nkwanta", "Nkwanta", "Bogoso"], "place": ["village", "village", "town"]},
                             geometry=[Point(600000, 600000), Point(650000, 650000), Point(700000, 700000)], crs=crs)
    districts = gpd.GeoDataFrame({"district": ["West", "East"]}, crs=crs, geometry=[
        Point(600000, 600000).buffer(20000), Point(650000, 650000).buffer(20000)])
    clusters = gpd.GeoDataFrame({"id": ["a", "b", "c", "d"], "ha": [4.0, 9.0, 2.0, 3.0]}, crs=crs, geometry=[
        Point(600500, 600000).buffer(100),  # 500 m from the first Nkwanta
        Point(601500, 600000).buffer(600),  # centre 1.5 km away but its edge is within 1 km
        Point(650000, 650900).buffer(50),   # second Nkwanta
        Point(703000, 700000).buffer(50),   # 3 km from Bogoso: not near
    ])
    t = places.towns_near(clusters, towns, districts)
    assert t[["name", "district", "ha", "patches"]].values.tolist() == [
        ["Nkwanta", "West", 13.0, 2], ["Nkwanta", "East", 2.0, 1]]
    assert t.ids.iloc[0] == ["b", "a"]  # largest first, for the picture
    assert round(t.lat.iloc[0], 3) and round(t.lon.iloc[0], 3)


def test_a_village_mapped_twice_counts_once_and_a_town_off_the_district_outlines_takes_the_nearest():
    crs = "EPSG:32630"
    towns = gpd.GeoDataFrame({"name": ["Nsuaem", "Nsuaem", "Takyikrom"], "place": ["village", "village", "village"]},
                             geometry=[Point(600000, 600000), Point(601100, 600000), Point(700000, 700000)], crs=crs)
    districts = gpd.GeoDataFrame({"district": ["West", "Lakeside"]}, crs=crs, geometry=[
        Point(600000, 600000).buffer(20000), Point(700000, 695000).buffer(4000)])
    clusters = gpd.GeoDataFrame({"id": ["a", "b"], "ha": [4.0, 2.0]}, crs=crs, geometry=[
        Point(600500, 600000).buffer(100), Point(700300, 700000).buffer(50)])
    t = places.towns_near(clusters, towns, districts)
    assert t[["name", "district", "ha"]].values.tolist() == [["Nsuaem", "West", 4.0], ["Takyikrom", "Lakeside", 2.0]]
