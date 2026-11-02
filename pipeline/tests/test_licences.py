import geopandas as gpd
from shapely.geometry import box

from tracker.licences import LARGE_SCALE, NONE, PROSPECTING, RESTRICTED, SMALL_SCALE, classify, licence_class


def test_gold_mining_lease_is_large_scale():
    assert licence_class("Mining Lease") == LARGE_SCALE


def test_small_scale_licence_is_small_scale():
    assert licence_class("Small Scale Licence (Obuasi District)") == SMALL_SCALE


def test_prospecting_licence_does_not_allow_mining():
    assert licence_class("Prospecting Licence (Foreign)") == PROSPECTING


def test_restricted_lease_for_stone_or_sand_is_its_own_class():
    # A quarry lease is a licence to mine stone or sand, not gold: neither "no licence" nor a gold lease
    assert licence_class("Restricted Mining Lease >25 acres (National)") == RESTRICTED
    assert licence_class("Restricted Mining Lease (Sand & Gravel)") == RESTRICTED
    assert licence_class("Restricted Mining Lease (Small Scale)") == RESTRICTED


def test_restricted_lease_without_minerals_listed_is_still_restricted():
    assert licence_class("Restricted Mining Lease (Ghanaian)") == RESTRICTED


def test_full_mining_lease_is_large_scale_whatever_the_mineral():
    # The type alone decides: a limestone or manganese Mining Lease is still a licence to mine
    assert licence_class("Mining Lease") == LARGE_SCALE


def _clusters(*geoms):
    return gpd.GeoDataFrame({"local_id": range(1, len(geoms) + 1)}, geometry=list(geoms), crs="EPSG:32630")


def _licences(*pairs):
    return gpd.GeoDataFrame({"cls": [c for c, _ in pairs]}, geometry=[g for _, g in pairs], crs="EPSG:32630")


def test_cluster_outside_every_licence_has_no_licence():
    out = classify(_clusters(box(0, 0, 10, 10)), _licences((LARGE_SCALE, box(100, 100, 200, 200))))
    assert out.tolist() == [NONE]


def test_largest_share_wins_over_a_more_permissive_smaller_share():
    cluster = box(0, 0, 10, 10)
    lic = _licences((LARGE_SCALE, box(0, 0, 3.4, 10)), (SMALL_SCALE, box(4, 0, 10, 10)))
    assert classify(_clusters(cluster), lic).tolist() == [SMALL_SCALE]


def test_equal_shares_go_to_the_more_permissive_licence():
    lic = _licences((PROSPECTING, box(0, 0, 5, 10)), (LARGE_SCALE, box(5, 0, 10, 10)))
    assert classify(_clusters(box(0, 0, 10, 10)), lic).tolist() == [LARGE_SCALE]


def test_overlap_under_a_quarter_counts_as_no_licence():
    lic = _licences((LARGE_SCALE, box(0, 0, 2, 10)))
    assert classify(_clusters(box(0, 0, 10, 10)), lic).tolist() == [NONE]


def test_overlapping_licences_of_the_same_class_are_not_double_counted():
    lic = _licences((PROSPECTING, box(0, 0, 10, 10)), (PROSPECTING, box(0, 0, 10, 10)))
    assert classify(_clusters(box(0, 0, 10, 10)), lic).tolist() == [PROSPECTING]
