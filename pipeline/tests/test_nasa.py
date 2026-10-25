import datetime as dt

from tracker.nasa import acquired, layer_urls, tile_of

TITLE = "OPERA_L3_DIST-ALERT-HLS_T30NXM_20261022T102049Z_20261024T052937Z_S2B_30_v1"


def test_tile_is_read_from_the_granule_title():
    assert tile_of(TITLE) == "T30NXM"


def test_acquisition_date_is_the_first_timestamp_not_the_production_date():
    assert acquired(TITLE) == dt.date(2026, 10, 22)


def test_layer_urls_are_keyed_by_layer_name_and_skip_s3_links():
    entry = {"title": TITLE, "links": [
        {"href": f"https://data.example/{TITLE}/{TITLE}_VEG-DIST-STATUS.tif"},
        {"href": f"s3://bucket/{TITLE}/{TITLE}_VEG-DIST-STATUS.tif"},
        {"href": f"https://data.example/{TITLE}/{TITLE}_VEG-DIST-DATE.tif"},
        {"href": f"https://data.example/{TITLE}/{TITLE}.cmr.xml"},
    ]}
    urls = layer_urls(entry)
    assert set(urls) == {"VEG-DIST-STATUS", "VEG-DIST-DATE"}
    assert urls["VEG-DIST-DATE"].startswith("https://")


def test_a_failed_read_is_retried(monkeypatch):
    import numpy as np
    import rasterio

    from tracker import nasa

    calls = {"n": 0}

    class Dataset:
        transform, crs = "t", "c"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, band):
            calls["n"] += 1
            if calls["n"] == 2:
                raise rasterio.errors.RasterioIOError("got 0 bytes")
            return np.zeros((2, 2), "uint8")

    monkeypatch.setattr(nasa, "gdal_env", dict)
    monkeypatch.setattr(nasa.rasterio, "open", lambda url: Dataset())
    monkeypatch.setattr(nasa.time, "sleep", lambda s: None)
    entry = {"title": TITLE, "links": [{"href": f"https://x/{TITLE}_VEG-DIST-STATUS.tif"},
                                        {"href": f"https://x/{TITLE}_VEG-DIST-DATE.tif"}]}
    date = nasa.read_status_and_date(entry)[1]
    assert date.dtype == np.int32 and calls["n"] == 4
