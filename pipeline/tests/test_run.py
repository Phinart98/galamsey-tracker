import pytest

from tracker.run import check_granules


def test_every_tile_with_a_granule_in_the_last_weeks_is_used():
    got = {"A": {"title": "a"}, "B": {"title": "b-older"}, "C": {"title": "not switched on"}}
    assert check_granules(["A", "B"], got) == {"A": {"title": "a"}, "B": {"title": "b-older"}}


def test_a_tile_with_no_granule_at_all_stops_the_run_so_its_places_are_not_dropped():
    with pytest.raises(RuntimeError, match="B"):
        check_granules(["A", "B"], {"A": {"title": "a"}})
