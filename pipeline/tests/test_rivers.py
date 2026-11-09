import itertools

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point

from tracker import rivers

CRS = "EPSG:32630"
# A river flowing due south for 20 km: downstream is -y, so its right bank is west (screen left on the page)
SOUTH = LineString([(600000, 620000), (600000, 600000)])


def test_a_point_west_of_a_south_flowing_river_is_on_its_right_bank_shown_on_the_left():
    assert rivers.offset(SOUTH, Point(599700, 610000)) == 300
    assert rivers.offset(SOUTH, Point(600400, 610000)) == -400


def test_a_band_row_runs_from_the_right_bank_to_the_left_across_two_kilometres():
    pts = rivers.band_points(SOUTH, 5000)
    assert len(pts) == 2 * rivers.HALF_M // rivers.STEP_M
    assert pts[0][0] < 600000 - 990 and pts[-1][0] > 600000 + 990   # west first
    assert np.allclose(pts[:, 1], 615000)


def test_the_guide_of_a_straight_river_is_the_river_and_the_picture_is_as_long():
    g = rivers.guide(SOUTH)
    assert abs(g.length - SOUTH.length) < 30
    assert rivers.km_left(SOUTH, g)[0] == 20.0
    assert rivers.km_left(SOUTH, g)[-1] == 0.0


def test_a_winding_river_is_longer_than_its_picture_and_km_left_counts_river_km():
    x = 600000 + 300 * np.sin(np.linspace(0, 40 * np.pi, 4000))
    wiggly = LineString(np.c_[x, np.linspace(620000, 600000, 4000)])
    g = rivers.guide(wiggly)
    left = rivers.km_left(wiggly, g)
    assert g.length < 0.8 * wiggly.length
    assert abs(left[0] - wiggly.length / 1000) < 0.1
    assert all(a >= b for a, b in itertools.pairwise(left))   # always fewer km to go further down


def test_a_sharp_kink_counts_as_one_jump_and_a_straight_line_none():
    kink = LineString([(0, 0), (0, 1000), (1000, 1000)])
    assert rivers.jumps(kink) == 1
    assert rivers.jumps(SOUTH) == 0


def test_bright_colourless_pixels_are_cloud_and_green_forest_is_not():
    rgb = np.zeros((40, 40, 3), np.uint8)
    rgb[:] = (40, 80, 40)
    rgb[20, 20] = (230, 230, 225)
    m = rivers.cloud_mask(rgb)
    assert m[20, 20] and m[20, 24]          # widened around the cloud
    assert not m[0, 0]


def test_the_newest_clear_day_is_used_and_the_previous_piece_keeps_its_day_if_nearly_as_new():
    days = [("2026-03-01", 0.99), ("2026-02-10", 0.98), ("2025-12-01", 0.995)]
    assert rivers.pick_day(days, prev=None) == "2026-03-01"
    assert rivers.pick_day(days, prev="2026-02-10") == "2026-02-10"   # same pass as the piece above: no seam
    assert rivers.pick_day(days, prev="2025-12-01") == "2026-03-01"   # three months older: newer wins


def test_with_no_clear_day_the_clearest_is_used_and_with_none_at_all_nothing():
    assert rivers.pick_day([("2026-03-01", 0.6), ("2026-01-01", 0.9)], prev=None) == "2026-01-01"
    assert rivers.pick_day([], prev=None) is None


def test_town_names_glued_together_in_osm_get_their_space_back():
    assert rivers.town_name("BimponAgya") == "Bimpon Agya"
    assert rivers.town_name("Dunkwa-on-Offin") == "Dunkwa-on-Offin"
    assert rivers.town_name("Twifo Praso") == "Twifo Praso"


def test_villages_are_marked_within_1_5_km_and_towns_within_5_km():
    s = gpd.GeoDataFrame({"name": ["Near", "Far", "Big", "Nameless"], "place": ["village", "village", "town", "village"]},
                         geometry=[Point(599000, 610000), Point(597000, 610000), Point(604000, 615000), Point(600100, 611000)],
                         crs=CRS)
    s.loc[3, "name"] = None
    got = rivers.towns(s, SOUTH)
    assert [t["name"] for t in got] == ["Big", "Near"]                 # in order down the river
    lon, lat = rivers.TO_LL.transform(599000, 610000)
    assert got[1] == {"name": "Near", "place": "village", "km": 10.0, "off_m": 1000, "water_m": 1000,
                      "lon": round(lon, 5), "lat": round(lat, 5)}


def test_a_village_is_kept_by_its_distance_from_the_water_not_from_the_middle_of_the_picture():
    s = gpd.GeoDataFrame({"name": ["Bend"], "place": ["village"]}, geometry=[Point(598000, 610000)], crs=CRS)
    water = LineString([(599000, 620000), (599000, 600000)])   # the river swings 1 km west of the picture's middle
    got = rivers.towns(s, SOUTH, water)
    assert got[0]["water_m"] == 1000 and got[0]["off_m"] == 2000


def test_a_place_within_1_km_of_a_river_gets_its_km_and_bank_and_the_nearest_river_first():
    east = LineString([(601500, 620000), (601500, 600000)])
    lines = {"west": (SOUTH, rivers.guide(SOUTH)), "east": (east, rivers.guide(east))}
    places = gpd.GeoSeries([Point(600800, 605000).buffer(50), Point(620000, 605000).buffer(50)], crs=CRS)
    got = rivers.river_places(places, lines)
    assert [r["slug"] for r in got[0]] == ["east", "west"]
    assert got[0][1]["off_m"] == -800 and abs(got[0][1]["km"] - 15) < 0.05 and got[0][1]["river_m"] == 750
    assert got[0][1]["in_picture"]
    assert got[1] == []


def test_the_zone_ends_where_the_river_leaves_it_for_good():
    assert rivers.zone_end_km([True, True, False, True, False, False]) == 2.0
    assert rivers.zone_end_km([True, True]) is None
    assert rivers.zone_end_km([False, False]) is None


def test_the_main_stem_follows_the_named_branch_even_when_another_drains_more():
    r = pd.DataFrame({"NEXT_DOWN": [0, 1, 1, 2, 3], "UPLAND_SKM": [900, 800, 850, 500, 20]}, index=[1, 2, 3, 4, 5])
    # 1 is the mouth; 2 (named) and 3 (bigger, unnamed) join at it; the walk goes up 2, then 4, and stops above 30 km2
    assert rivers.main_stem(r, 1, named={2, 4}) == [1, 2, 4]
    assert rivers.main_stem(r, 1, named=set()) == [1, 3]


def test_tiles_cut_the_picture_into_5_km_pieces_with_a_shorter_last_one():
    assert rivers.tile_rows(1230) == [(0, 500), (500, 1000), (1000, 1230)]


def test_a_place_near_the_water_but_past_the_picture_edge_is_marked_outside_it():
    water = LineString([(599000, 620000), (599000, 600000)])   # the river 1 km west of the picture's middle
    got = rivers.river_places(gpd.GeoSeries([Point(598200, 610000).buffer(50)], crs=CRS), {"r": (water, SOUTH)})
    assert got[0][0]["river_m"] == 750 and got[0][0]["in_picture"] is False


def _course_file(path, coords):
    import json
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"streams_km": 0},
                   "geometry": {"type": "LineString", "coordinates": coords}}]}, f)


def test_weekly_places_use_the_course_saved_with_the_published_pictures_not_a_newer_one(tmp_path, monkeypatch):
    import json
    courses, out = tmp_path / "courses", tmp_path / "out"
    (out / "rivers" / "pra" / "202601200417").mkdir(parents=True)
    courses.mkdir()
    _course_file(courses / "pra.geojson", [[-1.0, 6.0], [-1.0, 5.8]])   # remade since the pictures
    _course_file(out / "rivers" / "pra" / "202601200417" / "course.json", [[-1.2, 6.0], [-1.2, 5.8]])
    (out / "rivers" / "pra.json").write_text(json.dumps({"version": "202601200417"}))
    monkeypatch.setattr(rivers, "COURSES", str(courses))
    monkeypatch.setattr(rivers, "OUT", str(out))
    course, _ = rivers.lines()["pra"]
    lon, _ = rivers.TO_LL.transform(*course.coords[0])
    assert abs(lon - -1.2) < 1e-6
