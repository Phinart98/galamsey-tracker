import datetime as dt

import numpy as np
import pandas as pd
import pytest

from tracker.chips import hazy, usable_chip
from tracker.licences import LARGE_SCALE, NONE, PROSPECTING
from tracker.run import needs_chips
from tracker.summary import football_pitches, summarise


def _clusters():
    return pd.DataFrame([
        {"id": "a", "ha": 30.0, "licence": NONE, "district": "Wassa Amenfi East", "near": "Dadieso"},
        {"id": "b", "ha": 10.0, "licence": PROSPECTING, "district": "Wassa Amenfi East", "near": "Dadieso"},
        {"id": "c", "ha": 60.0, "licence": LARGE_SCALE, "district": "Obuasi Municipal", "near": "Obuasi"},
    ])


def test_football_pitches_uses_a_105_by_68_metre_pitch():
    assert football_pitches(0.714) == 1
    assert football_pitches(4046) == 5667


def test_summary_totals_and_licence_shares_add_up():
    s = summarise(_clusters(), top=2)
    assert s["total_ha"] == 100
    assert s["patches"] == 3
    assert s["by_licence"][NONE] == {"ha": 30, "share": 0.3}
    assert s["by_licence"][LARGE_SCALE] == {"ha": 60, "share": 0.6}
    assert sum(v["share"] for v in s["by_licence"].values()) == pytest.approx(1.0)


def test_summary_lists_every_licence_class_even_when_empty():
    s = summarise(_clusters(), top=2)
    assert s["by_licence"]["small-scale licence"] == {"ha": 0, "share": 0.0}


def test_no_licence_to_mine_combines_no_licence_and_prospecting_only():
    assert summarise(_clusters(), top=2)["no_licence_to_mine"] == {"ha": 40, "share": 0.4}


def test_top_places_are_largest_first_and_districts_are_summed():
    s = summarise(_clusters(), top=2)
    assert [p["id"] for p in s["top_places"]] == ["c", "a"]
    assert s["top_districts"][0] == {"district": "Obuasi Municipal", "ha": 60}
    assert s["top_districts"][1] == {"district": "Wassa Amenfi East", "ha": 40}


def test_summary_without_place_names_skips_districts():
    s = summarise(_clusters().drop(columns=["district", "near"]), top=0)
    assert s["total_ha"] == 100 and s["top_districts"] == []


def test_empty_week_summarises_to_zero_not_an_error():
    s = summarise(_clusters().iloc[0:0], top=2)
    assert s["total_ha"] == 0 and s["top_places"] == [] and s["no_licence_to_mine"]["share"] is None


def test_chip_with_clouds_over_ten_percent_is_rejected():
    scl = np.full((10, 10), 4)
    scl[0:2, :] = 9             # 20% high-probability cloud
    assert not usable_chip(scl)


def test_clear_chip_is_usable_and_shadows_count_as_cloud():
    scl = np.full((10, 10), 5)
    scl[0, :] = 3               # 10% cloud shadow: at the limit, still usable
    assert usable_chip(scl)
    scl[1, 0] = 3
    assert not usable_chip(scl)


def test_chip_with_missing_data_is_rejected():
    scl = np.full((10, 10), 4)
    scl[:, 0:1] = 0             # 10% no data, more than the 2% allowed
    assert not usable_chip(scl)


def test_grey_haze_that_the_scene_cloud_mask_missed_is_rejected():
    fog = np.full((100, 100, 3), 130, "uint8")
    fog[:, :, 1] = 140
    assert hazy(fog)


def test_bright_mining_ground_and_some_grey_tailings_are_not_haze():
    rgb = np.zeros((100, 100, 3), "uint8")
    rgb[:] = (40, 70, 35)               # forest
    rgb[:50] = (220, 190, 110)          # yellow pits and bare soil
    rgb[50:65] = (150, 150, 145)        # 15% grey tailings
    assert not hazy(rgb)


def test_places_without_a_clear_picture_are_retried_after_a_week():
    today = dt.date(2026, 10, 25)
    assert needs_chips({"active": True, "ha": 5.0, "chips": None}, today)
    assert needs_chips({"active": True, "ha": 5.0, "chips": {"missing": True, "checked": "2026-10-17"}}, today)
    assert not needs_chips({"active": True, "ha": 5.0, "chips": {"missing": True, "checked": "2026-10-20"}}, today)
    assert not needs_chips({"active": True, "ha": 5.0, "chips": {"before": {"date": "2025-02-04"}, "after": {"date": "2026-10-20"}}}, today)
    assert needs_chips({"active": True, "ha": 1.0, "chips": None}, today)  # every place gets pictures
    assert not needs_chips({"active": False, "ha": 5.0, "chips": None}, today)


def test_json_files_write_missing_values_as_null_not_nan(tmp_path):
    import json

    from tracker.run import _write_json
    path = tmp_path / "x.json"
    _write_json(str(path), {"near": float("nan"), "rows": [{"near_km": float("nan"), "ha": 2.5}]})
    text = path.read_text(encoding="utf-8")
    assert "NaN" not in text
    assert json.loads(text) == {"near": None, "rows": [{"near_km": None, "ha": 2.5}]}
