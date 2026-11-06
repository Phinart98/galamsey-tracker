import pytest

from tracker.run import granules_for


def test_a_tile_missing_from_the_recent_search_takes_its_newest_older_granule():
    recent = {"A": {"title": "a-new"}}
    older = {"A": {"title": "a-old"}, "B": {"title": "b-old"}}
    got = granules_for(["A", "B"], lambda days: recent if days == 12 else older)
    assert got == {"A": {"title": "a-new"}, "B": {"title": "b-old"}}


def test_a_tile_with_no_granule_at_all_stops_the_run_so_its_places_are_not_dropped():
    with pytest.raises(RuntimeError, match="B"):
        granules_for(["A", "B"], lambda days: {"A": {"title": "a"}})
