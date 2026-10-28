"""Can a plain rule tell mining from farms and roads? Tuned and scored on patches judged by eye (spike log s27).

The rule marks a patch "mining signs" when all of these hold (thresholds chosen from a small grid):
    bare >= B         most of the patch has no plants
    water > W         open water (ponds) inside or within 60 m
    elongation <= E   not a long thin strip (road, pipeline)
    green_now <= G    not greening again like a farm
Honest scoring: 200 random half splits. Thresholds are picked on one half (most patches caught while at least 90%
of marked ones are mining), then scored on the other half, which the thresholds never saw.

Run from the repo root after spike/signs_features.py: uv run --project pipeline python spike/signs_rule.py
"""
import glob
import itertools

import numpy as np
import pandas as pd

PASS_PRECISION = 0.90
GRID = {
    "B": [0.0, 0.3, 0.5, 0.7],
    "W": [-1.0, 0.0, 0.01, 0.02, 0.05, 0.1],  # -1: no water condition; 0: any open water at all
    "E": [99, 6, 4, 3],
    "G": [1.0, 0.4, 0.3, 0.2],
}


def marks(df, B, W, E, G):
    return (df.bare >= B) & (df.water > W) & (df.elongation <= E) & (df.green_now <= G)


def score(df, rule):
    m = marks(df, *rule)
    hit = int((m & (df.label == "mining")).sum())
    return {"marked": int(m.sum()), "precision": hit / m.sum() if m.sum() else np.nan,
            "recall": hit / (df.label == "mining").sum(), "nots_marked": int((m & (df.label == "not")).sum())}


def best(df):
    """The rule that catches the most mining while keeping precision at the bar (ties: the simpler, looser rule)."""
    top, top_key = None, None
    for rule in itertools.product(*GRID.values()):
        s = score(df, rule)
        if s["marked"] < 5 or not s["precision"] >= PASS_PRECISION:
            continue
        key = (s["recall"], s["precision"])
        if top_key is None or key > top_key:
            top, top_key = rule, key
    return top


def main():
    df = pd.concat([pd.read_csv(f) for f in glob.glob("pipeline/out/checks/signs/features*.csv")], ignore_index=True)
    df = df.drop_duplicates("key")
    print(f"{len(df)} measured patches: {(df.label == 'mining').sum()} mining, {(df.label == 'not').sum()} not")
    print(f"mark everything: precision {(df.label == 'mining').mean():.0%}\n")
    print(df.groupby("label")[["bare", "bright", "water", "green_now", "elongation", "compact"]].median().round(3), "\n")

    rng = np.random.default_rng(27)
    held = []
    for _ in range(200):
        idx = rng.permutation(len(df))
        train, test = df.iloc[idx[: len(df) // 2]], df.iloc[idx[len(df) // 2:]]
        rule = best(train)
        if rule is None:
            held.append({"marked": 0, "precision": np.nan, "recall": 0.0, "nots_marked": 0})
            continue
        held.append(score(test, rule))
    h = pd.DataFrame(held)
    print("held-out halves (200 splits):")
    print(f"  precision median {h.precision.median():.0%}, 10th percentile {h.precision.quantile(0.1):.0%}, "
          f"share of splits at or above {PASS_PRECISION:.0%}: {(h.precision >= PASS_PRECISION).mean():.0%}")
    print(f"  recall median {h.recall.median():.0%}; non-mining patches marked per half: median {h.nots_marked.median():.0f}")

    final = best(df)
    print("\nrule tuned on all patches:", dict(zip("BWEG", final)) if final else None)
    if final:
        print("  on all patches:", {k: round(v, 3) if isinstance(v, float) else v for k, v in score(df, final).items()})
        print("  non-mining patches it still marks:")
        print(df[marks(df, *final) & (df.label == "not")][["key", "ha", "bare", "water", "green_now", "elongation"]].to_string())


if __name__ == "__main__":
    main()
