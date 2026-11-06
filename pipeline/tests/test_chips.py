from types import SimpleNamespace

import numpy as np
from rasterio.errors import RasterioIOError

from tracker import chips


def _item(name):
    return SimpleNamespace(assets={"scl": SimpleNamespace(href=f"{name}/scl"), "visual": SimpleNamespace(href=f"{name}/rgb")})


def test_a_scene_whose_file_cannot_be_read_is_skipped_not_fatal(monkeypatch):
    def read(href, bbox):
        if href.startswith("broken"):
            raise RasterioIOError("not recognized as being in a supported file format")
        if href.endswith("scl"):
            return np.full((1, 4, 4), 4, dtype=np.uint8)
        return np.full((3, 4, 4), 60, dtype=np.uint8)

    monkeypatch.setattr(chips, "_read", read)
    assert chips.scene(_item("broken"), []) is None
    assert chips.scene(_item("good"), []).shape == (4, 4, 3)


def test_a_network_failure_on_one_place_skips_it_and_the_run_carries_on(monkeypatch, tmp_path):
    import datetime as dt
    import json

    from tracker import run

    rec = {"active": True, "ha": 10.0, "lon": -2.0, "lat": 6.0, "first_seen": "2026-05-01", "last_seen": "2026-09-01"}
    (tmp_path / "places").mkdir()
    (tmp_path / "places" / "index.json").write_text(json.dumps({"a": {**rec, "id": "a", "ha": 20.0}, "b": {**rec, "id": "b"}}))
    calls = []

    def clearest(lon, lat, half_km, start, end):
        calls.append(1)
        if len(calls) == 1:
            raise ConnectionError("Failed to resolve 'earth-search.aws.element84.com'")

    monkeypatch.setattr(run, "OUT", str(tmp_path))
    monkeypatch.setattr(run.chips, "clearest", clearest)
    run.make_chips(dt.date(2026, 10, 25), limit=10)
    index = json.loads((tmp_path / "places" / "index.json").read_text())
    assert "chips" not in index["a"]  # untouched, so it is tried again next run
    assert index["b"]["chips"] == {"missing": True, "checked": "2026-10-25"}


def test_encode_makes_one_720_webp():
    # Two files per place (before and after) keeps the pictures under Cloudflare Pages' 20,000-file limit
    out = chips.encode(np.full((40, 40, 3), 90, dtype=np.uint8))
    assert sorted(out) == ["720.webp"]
    assert all(blob[8:12] == b"WEBP" for blob in out.values())


def test_the_same_scene_from_both_collections_is_tried_once_least_cloudy_first():
    import datetime as dt
    from types import SimpleNamespace

    from tracker import chips

    def item(day, tile, cloud):
        return SimpleNamespace(datetime=dt.datetime(2026, 1, day, 10, 30), properties={"grid:code": tile, "eo:cloud_cover": cloud})
    c1 = [item(5, "MGRS-30NXM", 20), item(9, "MGRS-30NXM", 2)]
    old = [item(5, "MGRS-30NXM", 21), item(7, "MGRS-30NXM", 9)]
    got = chips.unique_scenes([c1, old])
    assert [(i.datetime.day, i.properties["eo:cloud_cover"]) for i in got] == [(9, 2), (7, 9), (5, 20)]


def test_copies_of_one_scene_a_moment_apart_across_a_minute_still_count_once():
    import datetime as dt
    from types import SimpleNamespace

    from tracker import chips
    c1 = SimpleNamespace(datetime=dt.datetime(2026, 1, 5, 10, 39, 59), properties={"grid:code": "MGRS-30NXM", "eo:cloud_cover": 5})
    old = SimpleNamespace(datetime=dt.datetime(2026, 1, 5, 10, 40, 1), properties={"grid:code": "MGRS-30NXM", "eo:cloud_cover": 5})
    assert chips.unique_scenes([[c1], [old]]) == [c1]
