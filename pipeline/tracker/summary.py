"""The numbers the site prints, computed in one place so every page agrees."""
import pandas as pd

from tracker.licences import LARGE_SCALE, NONE, PROSPECTING, SMALL_SCALE

PITCH_HA = 0.714  # a 105 x 68 m football pitch
CLASSES = (NONE, PROSPECTING, SMALL_SCALE, LARGE_SCALE)


def football_pitches(ha: float) -> int:
    return round(ha / PITCH_HA)


def _share(part: float, total: float) -> float | None:
    return round(part / total, 3) if total else None


def summarise(clusters: pd.DataFrame, top: int = 10) -> dict:
    total = float(clusters.ha.sum()) if len(clusters) else 0.0
    by = clusters.groupby("licence").ha.sum() if len(clusters) else pd.Series(dtype=float)
    by_licence = {c: {"ha": round(float(by.get(c, 0.0))), "share": _share(float(by.get(c, 0.0)), total) or 0.0}
                  for c in CLASSES}
    unlicensed = float(by.get(NONE, 0.0) + by.get(PROSPECTING, 0.0))
    places = clusters.sort_values("ha", ascending=False).head(top)
    districts = (clusters.groupby("district").ha.sum().sort_values(ascending=False).head(top)
                 if len(clusters) and "district" in clusters else pd.Series(dtype=float))
    return {
        "total_ha": round(total),
        "football_pitches": football_pitches(total),
        "patches": len(clusters),
        "by_licence": by_licence,
        "no_licence_to_mine": {"ha": round(unlicensed), "share": _share(unlicensed, total)},
        "top_places": [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in row.items() if k != "geometry"}
                       for row in places.to_dict("records")],
        "top_districts": [{"district": d, "ha": round(float(h))} for d, h in districts.items()],
    }
