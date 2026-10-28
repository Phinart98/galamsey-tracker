import datetime as dt

import numpy as np

from tracker import signs

TODAY = dt.date(2026, 10, 28)


def _scene(green, swir16, scl=4, shape=(5, 5)):
    return {"green": np.full(shape, green, dtype="float32"), "swir16": np.full(shape, swir16, dtype="float32")}, np.full(shape, scl)


def test_water_scores_above_zero_and_soil_below():
    assert signs.mndwi(np.array([900.0]), np.array([200.0]))[0] > 0  # water: some green back, almost no shortwave infrared
    assert signs.mndwi(np.array([900.0]), np.array([2500.0]))[0] < 0  # bare soil reflects shortwave infrared strongly


def test_only_pixels_in_the_ring_around_the_patch_count():
    bands, scl = _scene(900, 2500)
    bands["green"][0, 0], bands["swir16"][0, 0] = 900, 100  # a pond in the corner
    near = np.zeros((5, 5), bool)
    near[:2, :2] = True
    assert signs.water_share(bands, scl, near) == 0.25
    near[:] = False
    near[3:, 3:] = True
    assert signs.water_share(bands, scl, near) == 0.0


def test_a_cloudy_ring_gives_no_reading():
    bands, scl = _scene(900, 100)
    scl[0, :] = 9  # one row of five is cloud: 20%
    assert signs.water_share(bands, scl, np.ones((5, 5), bool)) is None


def test_only_active_places_with_no_licence_to_mine_are_measured():
    rec = {"active": True, "licence": "no licence"}
    assert signs.needs_reading(rec, TODAY)
    assert signs.needs_reading({**rec, "licence": "prospecting only"}, TODAY)
    assert not signs.needs_reading({**rec, "licence": "large-scale lease"}, TODAY)
    assert not signs.needs_reading({**rec, "active": False}, TODAY)
    assert not signs.needs_reading({**rec, "signs": {"water": 0.1, "scene": "2026-10-01"}}, TODAY)


def test_a_place_with_no_clear_scene_is_tried_again_after_a_week():
    rec = {"active": True, "licence": "no licence", "signs": {"missing": True, "checked": "2026-10-25"}}
    assert not signs.needs_reading(rec, TODAY)
    assert signs.needs_reading(rec, TODAY + dt.timedelta(days=4))


def test_likely_galamsey_needs_open_water_and_no_licence_to_mine():
    assert signs.likely_galamsey("no licence", 0.02)
    assert signs.likely_galamsey("prospecting only", 0.3)
    assert not signs.likely_galamsey("no licence", 0.0)
    assert not signs.likely_galamsey("small-scale licence", 0.3)
    assert not signs.likely_galamsey("no licence", None)


def _places(tmp_path, recs):
    import json

    import geopandas as gpd
    from shapely.geometry import box

    (tmp_path / "places").mkdir()
    (tmp_path / "places" / "index.json").write_text(json.dumps({r["id"]: r for r in recs}))
    gpd.GeoDataFrame({"id": [r["id"] for r in recs]}, geometry=[box(-2, 6, -1.99, 6.01)] * len(recs), crs=4326) \
        .to_file(tmp_path / "places" / "latest.geojson", driver="GeoJSON")


def _index(tmp_path):
    import json
    return json.loads((tmp_path / "places" / "index.json").read_text())


def test_the_run_measures_the_largest_first_and_sets_the_flag(monkeypatch, tmp_path):
    from tracker import run

    base = {"active": True, "licence": "no licence", "first_seen": "2026-05-01"}
    _places(tmp_path, [{**base, "id": "small", "ha": 1.0}, {**base, "id": "big", "ha": 9.0},
                       {**base, "id": "dry", "ha": 5.0}, {**base, "id": "leased", "ha": 50.0, "licence": "large-scale lease"}])
    seen = []

    def reading(poly, first_seen, today):
        seen.append(1)
        return {"water": 0.0 if len(seen) == 2 else 0.1, "scene": "2026-09-01"}

    monkeypatch.setattr(run, "OUT", str(tmp_path))
    monkeypatch.setattr(run.signs, "reading", reading)
    run.make_signs(TODAY, limit=2, workers=1)
    index = _index(tmp_path)
    assert index["big"]["likely_galamsey"] is True
    assert index["dry"]["likely_galamsey"] is False
    assert "signs" not in index["small"] and "signs" not in index["leased"]


def test_a_network_failure_leaves_the_place_for_next_run(monkeypatch, tmp_path):
    from tracker import run

    _places(tmp_path, [{"id": "a", "active": True, "licence": "no licence", "first_seen": "2026-05-01", "ha": 2.0}])

    def reading(poly, first_seen, today):
        raise ConnectionError("Failed to resolve 'earth-search.aws.element84.com'")

    monkeypatch.setattr(run, "OUT", str(tmp_path))
    monkeypatch.setattr(run, "SIGNS_RETRY_WAITS", (0, 0, 0))
    monkeypatch.setattr(run.signs, "reading", reading)
    run.make_signs(TODAY, limit=5, workers=1)
    assert "signs" not in _index(tmp_path)["a"]


def test_no_clear_scene_is_recorded_so_it_waits_a_week(monkeypatch, tmp_path):
    from tracker import run

    _places(tmp_path, [{"id": "a", "active": True, "licence": "no licence", "first_seen": "2026-05-01", "ha": 2.0}])
    monkeypatch.setattr(run, "OUT", str(tmp_path))
    monkeypatch.setattr(run.signs, "reading", lambda poly, first_seen, today: None)
    run.make_signs(TODAY, limit=5, workers=1)
    assert _index(tmp_path)["a"]["signs"] == {"missing": True, "checked": "2026-10-28"}
    assert _index(tmp_path)["a"]["likely_galamsey"] is False


def test_a_place_refused_twice_by_the_picture_service_is_tried_again_and_kept(monkeypatch, tmp_path):
    from pystac_client.exceptions import APIError

    from tracker import run

    _places(tmp_path, [{"id": "a", "active": True, "licence": "no licence", "first_seen": "2026-05-01", "ha": 2.0}])
    calls = []

    def reading(poly, first_seen, today):
        calls.append(1)
        if len(calls) < 3:
            raise APIError("429 Too Many Requests")
        return {"water": 0.2, "scene": "2026-09-01"}

    monkeypatch.setattr(run, "OUT", str(tmp_path))
    monkeypatch.setattr(run, "SIGNS_RETRY_WAITS", (0, 0, 0))
    monkeypatch.setattr(run.signs, "reading", reading)
    run.make_signs(TODAY, limit=5, workers=1)
    assert _index(tmp_path)["a"]["signs"] == {"water": 0.2, "scene": "2026-09-01"}
