import datetime as dt

import numpy as np
from rasterio.transform import from_origin

from tracker.dist import cluster_polygons, decode_date, loss_mask, reading_days, window_mask

T = from_origin(600000, 700020, 30, 30)


def test_decode_date_counts_days_from_end_of_2020():
    assert decode_date(1) == dt.date(2021, 1, 1)
    assert decode_date(2121) == dt.date(2026, 10, 22)


def test_loss_mask_keeps_only_confirmed_heavy_loss_inside_the_window():
    status = np.array([[6, 8, 3, 6]])
    date = np.array([[2121, 1800, 2121, 1700]])
    window_end = decode_date(2121)
    mask = loss_mask(status, date, window_end, days=365)
    # 6 and 8 are confirmed loss of at least half the plant cover; 3 is under half; 1700 is too old
    assert mask.tolist() == [[True, True, False, False]]


def test_loss_mask_ignores_dates_after_the_window_end():
    status = np.array([[6]])
    date = np.array([[2200]])
    assert not loss_mask(status, date, decode_date(2121), days=365).any()


def test_cluster_polygons_drops_patches_under_one_hectare():
    mask = np.zeros((20, 20), bool)
    mask[0:4, 0:3] = True       # 12 pixels = 1.08 ha, kept
    mask[10:12, 10:12] = True   # 4 pixels = 0.36 ha, dropped
    date = np.full(mask.shape, 2000)
    gdf = cluster_polygons(mask, date, T, "EPSG:32630", min_ha=1.0)
    assert len(gdf) == 1
    assert gdf.iloc[0].ha == 1.08


def test_cluster_polygons_joins_diagonal_neighbours_and_records_first_and_last_dates():
    mask = np.zeros((6, 6), bool)
    mask[0:3, 0:3] = True       # two 3x3 blocks touching only at one corner
    mask[3:6, 3:6] = True
    date = np.where(mask, 1900, 0)
    date[5, 5] = 2100
    gdf = cluster_polygons(mask, date, T, "EPSG:32630", min_ha=1.0)
    assert len(gdf) == 1
    assert gdf.iloc[0].ha == 1.62
    assert gdf.iloc[0].first_seen == str(decode_date(1900))
    assert gdf.iloc[0].last_seen == str(decode_date(2100))


def test_cluster_polygons_sorts_largest_first_with_stable_ids():
    mask = np.zeros((30, 30), bool)
    mask[0:4, 0:4] = True       # 16 px
    mask[10:16, 10:16] = True   # 36 px
    date = np.full(mask.shape, 2000)
    gdf = cluster_polygons(mask, date, T, "EPSG:32630", min_ha=1.0)
    assert gdf.ha.tolist() == [3.24, 1.44]
    assert gdf.local_id.tolist() == [1, 2]


def test_window_mask_adds_pixels_confirmed_after_the_window_ended():
    end = decode_date(2121)
    on_the_day = (np.array([[6, 3]]), np.array([[2000, 2110]]))   # second pixel not yet confirmed
    later = (np.array([[0, 6]]), np.array([[0, 2110]]))           # first pixel has expired, second is confirmed
    mask, date = window_mask([on_the_day, later], end)
    assert mask.tolist() == [[True, True]]
    assert date.tolist() == [[2000, 2110]]


def test_window_mask_ignores_later_readings_of_loss_that_began_after_the_window():
    end = decode_date(2121)
    later = (np.array([[6]]), np.array([[2150]]))
    mask, _ = window_mask([(np.array([[0]]), np.array([[0]])), later], end)
    assert not mask.any()


def test_reading_days_are_the_window_end_and_two_and_four_months_later_once_passed():
    end = dt.date(2026, 3, 22)
    assert reading_days(end, today=dt.date(2026, 10, 25)) == (
        [end, dt.date(2026, 5, 22), dt.date(2026, 7, 22)], True)
    assert reading_days(end, today=dt.date(2026, 6, 1)) == ([end, dt.date(2026, 5, 22)], False)


def test_reading_days_cross_the_new_year():
    assert reading_days(dt.date(2025, 11, 22), today=dt.date(2026, 10, 25))[0][-1] == dt.date(2026, 3, 22)


def test_a_settled_point_is_kept_only_while_the_tiles_it_covers_are_unchanged():
    from tracker.run import needs_point
    point = {"settled": True, "covered": ["T30NXM"]}
    assert not needs_point(point, ["T30NXM"])
    assert needs_point(point, ["T30NXM", "T30NXN"])
    assert needs_point({"settled": False, "covered": ["T30NXM"]}, ["T30NXM"])
    assert needs_point({"settled": True, "tiles": ["T30NXM"]}, ["T30NXM"])  # written before tiles were tracked
    assert needs_point(None, ["T30NXM"])
