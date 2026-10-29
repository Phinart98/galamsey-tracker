"""When a finished picture or water reading is out of date and should be taken again.

Pictures and readings are made once per place. A place that keeps growing would otherwise show an old "after"
picture and keep a label read before most of the digging, so both are redone when the place has grown by half
since, or has kept growing for three months. A retake that finds no clear picture keeps the old one and waits
another three months.
"""
import datetime as dt
from collections.abc import Callable, Iterable

GROWTH = 1.5
DAYS = 90


def due(done: dict, rec: dict, taken: str, today: dt.date) -> bool:
    """True if `done` (a picture pair or reading, taken on day `taken`) should be redone for place `rec`."""
    if done.get("ha") and rec.get("ha", 0) >= GROWTH * done["ha"]:
        return True
    last_try = max(taken, done.get("checked", taken))
    still_growing = rec.get("last_seen", "") > taken
    return still_growing and (today - dt.date.fromisoformat(last_try)).days >= DAYS


def queue(records: Iterable[dict], needs: Callable[[dict], bool], key: str) -> list[dict]:
    """Places that need work: those with nothing yet first, then retakes, each largest first."""
    todo = [r for r in records if needs(r)]
    return sorted(todo, key=lambda r: (bool(r.get(key)) and not r[key].get("missing"), -r["ha"]))
