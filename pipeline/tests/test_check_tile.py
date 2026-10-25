import pandas as pd

from tracker.check_tile import sample


def test_sample_takes_half_large_and_half_small_patches_repeatably():
    clusters = pd.DataFrame({"ha": [10.0] * 30 + [1.5] * 30})
    picks = sample(clusters, 20, seed=7)
    assert sum(p.ha >= 3 for p in picks) == 10 and sum(p.ha < 3 for p in picks) == 10
    assert [p.name for p in picks] == [p.name for p in sample(clusters, 20, seed=7)]


def test_sample_fills_from_small_patches_when_there_are_few_large_ones():
    clusters = pd.DataFrame({"ha": [10.0] * 3 + [1.5] * 30})
    assert len(sample(clusters, 20, seed=7)) == 20
