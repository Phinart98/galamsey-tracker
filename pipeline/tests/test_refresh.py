import datetime as dt

from tracker import refresh, signs
from tracker.run import needs_chips

TODAY = dt.date(2026, 10, 29)


def _pictured(ha_then=10.0, after="2026-10-01", **extra):
    return {"before": {"date": "2025-02-04"}, "after": {"date": after}, "ha": ha_then, **extra}


def test_a_place_that_grew_by_half_is_pictured_again():
    rec = {"active": True, "ha": 15.0, "last_seen": "2026-10-20", "chips": _pictured(10.0)}
    assert needs_chips(rec, TODAY)
    assert not needs_chips({**rec, "ha": 14.0}, TODAY)


def test_a_place_still_growing_after_three_months_is_pictured_again():
    rec = {"active": True, "ha": 10.5, "last_seen": "2026-10-20", "chips": _pictured(10.0, after="2026-07-20")}
    assert needs_chips(rec, TODAY)
    # Not growing since the picture: the old picture still shows it as it is
    assert not needs_chips({**rec, "last_seen": "2026-07-01"}, TODAY)
    # Less than three months since the picture
    assert not needs_chips({**rec, "chips": _pictured(10.0, after="2026-08-20")}, TODAY)


def test_a_retake_with_no_clear_picture_waits_three_months_before_the_next_try():
    rec = {"active": True, "ha": 10.5, "last_seen": "2026-10-20",
           "chips": _pictured(10.0, after="2026-06-01", checked="2026-09-01")}
    assert not needs_chips(rec, TODAY)


def test_pictures_made_before_sizes_were_kept_use_the_time_rule_only():
    rec = {"active": True, "ha": 50.0, "last_seen": "2026-10-20", "chips": {"before": {"date": "2025-02-04"}, "after": {"date": "2026-10-01"}}}
    assert not needs_chips(rec, TODAY)
    assert needs_chips({**rec, "chips": {**rec["chips"], "after": {"date": "2026-07-01"}}}, TODAY)


def test_new_places_come_before_retakes():
    new = {"id": "a", "active": True, "ha": 4.0, "chips": None}
    retake = {"id": "b", "active": True, "ha": 90.0, "last_seen": "2026-10-20", "chips": _pictured(10.0)}
    assert [r["id"] for r in refresh.queue([retake, new], lambda r: needs_chips(r, TODAY), "chips")] == ["a", "b"]


def test_a_water_reading_is_redone_when_the_place_grew_by_half():
    rec = {"active": True, "licence": "no licence", "ha": 6.0, "last_seen": "2026-10-20",
           "signs": {"water": 0.0, "scene": "2026-10-01", "ha": 4.0}}
    assert signs.needs_reading(rec, TODAY)
    assert not signs.needs_reading({**rec, "ha": 5.0}, TODAY)


def test_a_retake_keeps_the_before_picture_and_replaces_the_after(monkeypatch, tmp_path):
    import json

    import numpy as np

    from tracker import run

    old = {"before": {"date": "2025-02-04", "files": {"720.webp": "chips/a/before-720.webp"}},
           "after": {"date": "2026-06-01", "files": {"720.webp": "chips/a/after-720.webp"}}, "ha": 10.0}
    rec = {"id": "a", "active": True, "ha": 20.0, "first_seen": "2025-03-01", "last_seen": "2026-10-20",
           "lon": -2.0, "lat": 6.0, "chips": old}
    (tmp_path / "places").mkdir()
    (tmp_path / "places" / "index.json").write_text(json.dumps({"a": rec}))
    asked = []

    def clearest(lon, lat, half_km, start, end):
        asked.append((start, end))
        return dt.date(2026, 10, 22), np.full((8, 8, 3), 90, dtype=np.uint8)

    monkeypatch.setattr(run, "OUT", str(tmp_path))
    monkeypatch.setattr(run.chips, "clearest", clearest)
    run.make_chips(TODAY, limit=5)
    got = json.loads((tmp_path / "places" / "index.json").read_text())["a"]["chips"]
    assert len(asked) == 1  # only the after picture is searched for
    assert got["before"] == old["before"]
    assert got["after"]["date"] == "2026-10-22"
    assert got["ha"] == 20.0
