"""Discover Sentinel-1 RTC scenes for a (bbox, datetime-range) from
Microsoft Planetary Computer.

MPC is anonymous for the sentinel-1-rtc collection -- no key needed.
Asset hrefs are signed lazily via the pystac_client `modifier=` hook (the
canonical 2025 pattern used by Microsoft's own PlanetaryComputerExamples
notebooks). Signed URLs have ~1h TTL; stackstac consumes them during the
dask compute, with `errors_as_nodata` in threshold.py degrading transient
short-reads to NaN instead of aborting the whole job.
"""

from datetime import date

import planetary_computer
import structlog
from pystac import Item
from pystac_client import Client

log = structlog.get_logger()

PC_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-1-rtc"


def query_scenes(
    bbox: tuple[float, float, float, float],
    period_start: date,
    period_end: date,
) -> list[Item]:
    """Return signed pystac Items for the bbox over [period_start, period_end).

    Both VV and VH polarisations are required (Forkuor 2020 joint-mask logic).
    MPC's sentinel-1-rtc collection has both as separate assets ('vv', 'vh')
    on every IW-mode item, which is what we filter on.
    """
    client = Client.open(PC_STAC_URL, modifier=planetary_computer.sign_inplace)
    # STAC API interprets bare-date interval endpoints as T00:00:00Z, which
    # silently drops same-day acquisitions on `period_end` (Sentinel-1 IW
    # ascending passes over Ghana fire 18:00-22:00 UTC). Use explicit UTC
    # timestamps so the interval covers the full day at both ends.
    dt_from = f"{period_start.isoformat()}T00:00:00Z"
    dt_to = f"{period_end.isoformat()}T23:59:59Z"
    search = client.search(
        collections=[COLLECTION],
        bbox=bbox,
        datetime=f"{dt_from}/{dt_to}",
        query={
            "sar:instrument_mode": {"eq": "IW"},
            "s1:processing_level": {"eq": "1"},
        },
    )
    items: list[Item] = list(search.items())
    log.info(
        "STAC search",
        collection=COLLECTION,
        bbox=bbox,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        n_items=len(items),
    )
    return items
