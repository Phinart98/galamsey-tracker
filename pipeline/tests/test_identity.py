import geopandas as gpd
from shapely.geometry import Point, box

from tracker.identity import dedupe_tiles, make_id, match_ids

CRS = "EPSG:32630"


def _gdf(rows):
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS)


def test_make_id_is_readable_and_deterministic():
    assert make_id(-2.01341, 5.81291, "2025-11-13") == "2025-11-5813n2013w"
    assert make_id(-2.01341, 5.81291, "2025-11-13") == make_id(-2.01341, 5.81291, "2025-11-13")


def test_same_patch_seen_from_two_overlapping_tiles_is_kept_once():
    a = _gdf([{"tile": "T30NXM", "ha": 10.0, "geometry": box(0, 0, 100, 100)}])
    b = _gdf([{"tile": "T30NWM", "ha": 9.5, "geometry": box(5, 0, 100, 100)}])
    out = dedupe_tiles([a, b])
    assert len(out) == 1
    assert out.iloc[0].tile == "T30NXM"


def test_separate_patches_from_different_tiles_are_both_kept():
    a = _gdf([{"tile": "T30NXM", "ha": 10.0, "geometry": box(0, 0, 100, 100)}])
    b = _gdf([{"tile": "T30NWM", "ha": 4.0, "geometry": box(500, 500, 600, 600)}])
    assert len(dedupe_tiles([a, b])) == 2


def test_new_patch_without_history_gets_a_fresh_id_and_seed():
    new = _gdf([{"ha": 3.0, "first_seen": "2026-10-01", "geometry": box(0, 0, 100, 100)}])
    out, aliases = match_ids(new, previous=None, to_lonlat=lambda x, y: (-2.0, 5.8))
    assert out.iloc[0].id == "2026-10-5800n2000w"
    assert out.iloc[0].seed.within(new.iloc[0].geometry)
    assert aliases == {}


def test_growing_patch_keeps_its_id_while_it_still_holds_its_seed():
    prev = _gdf([{"id": "2025-11-5813n2013w", "first_seen": "2025-11-13", "geometry": Point(50, 50)}])
    new = _gdf([{"ha": 30.0, "first_seen": "2025-11-13", "geometry": box(0, 0, 300, 300)}])
    out, _ = match_ids(new, prev, to_lonlat=lambda x, y: (0, 0))
    assert out.iloc[0].id == "2025-11-5813n2013w"
    assert out.iloc[0].seed.equals(Point(50, 50))


def test_merged_patches_keep_the_older_id_and_alias_the_younger():
    prev = _gdf([
        {"id": "2025-12-a", "first_seen": "2025-12-01", "geometry": Point(250, 50)},
        {"id": "2025-11-b", "first_seen": "2025-11-01", "geometry": Point(50, 50)},
    ])
    new = _gdf([{"ha": 40.0, "first_seen": "2025-11-01", "geometry": box(0, 0, 300, 100)}])
    out, aliases = match_ids(new, prev, to_lonlat=lambda x, y: (0, 0))
    assert out.iloc[0].id == "2025-11-b"
    assert aliases == {"2025-12-a": "2025-11-b"}


def test_a_patch_dropped_as_a_duplicate_cannot_knock_out_a_third_one():
    big = _gdf([{"tile": "T30NXM", "ha": 10.0, "geometry": box(0, 0, 100, 100)},
                {"tile": "T30NXM", "ha": 6.0, "geometry": box(100, 0, 140, 100)}])
    middle = _gdf([{"tile": "T30NWM", "ha": 8.0, "geometry": box(20, 0, 140, 100)}])
    out = dedupe_tiles([big, middle])
    assert sorted(out.ha.tolist()) == [6.0, 10.0]


def test_same_tile_patches_are_never_merged_even_when_they_touch():
    a = _gdf([{"tile": "T30NXM", "ha": 5.0, "geometry": box(0, 0, 100, 100)},
              {"tile": "T30NXM", "ha": 4.0, "geometry": box(0, 0, 100, 90)}])
    assert len(dedupe_tiles([a])) == 2


def test_an_old_seed_inside_two_patches_gives_them_two_different_ids():
    # Tile copies that overlap by less than half are both kept, and an old seed can sit inside both
    prev = _gdf([{"id": "2025-11-old", "first_seen": "2025-11-01", "geometry": Point(50, 50)}])
    new = _gdf([{"ha": 10.0, "first_seen": "2025-11-01", "geometry": box(0, 0, 100, 100)},
                {"ha": 6.0, "first_seen": "2025-11-01", "geometry": box(40, 40, 140, 100)}])
    out, _ = match_ids(new, prev, to_lonlat=lambda x, y: (-2.0, 5.8))
    assert out.id.tolist()[0] == "2025-11-old"
    assert out.id.is_unique


def test_a_new_id_never_reuses_an_old_place_id():
    # An old place that is no longer active keeps its id, so a new patch on the same spot must not take it over
    prev = _gdf([{"id": "2026-10-5800n2000w", "first_seen": "2026-10-01", "geometry": Point(900, 900)}])
    new = _gdf([{"ha": 3.0, "first_seen": "2026-10-01", "geometry": box(0, 0, 100, 100)}])
    out, _ = match_ids(new, prev, to_lonlat=lambda x, y: (-2.0, 5.8))
    assert out.iloc[0].id == "2026-10-5800n2000w-2"


def test_aliases_point_at_the_end_of_a_chain_and_drop_old_ids_that_came_back():
    from tracker.identity import resolve_aliases
    aliases = {"a": "b", "b": "c", "d": "e", "x": "y", "y": "x"}
    # a merged into b, which later merged into c. d came back as a place of its own. x and y point at each other.
    assert resolve_aliases(aliases, active={"c", "d", "e"}) == {"a": "c", "b": "c"}
