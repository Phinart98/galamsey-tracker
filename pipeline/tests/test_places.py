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
