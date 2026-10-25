"""OPERA DIST-ALERT-HLS rules: which pixels count as recent heavy loss, and how they become patches."""
import datetime as dt

import geopandas as gpd
import numpy as np
from rasterio.features import shapes
from scipy import ndimage
from shapely.geometry import shape
from shapely.ops import unary_union

EPOCH = dt.date(2020, 12, 31)  # VEG-DIST-DATE counts days from here
CONFIRMED_HEAVY_LOSS = (6, 8)   # VEG-DIST-STATUS: confirmed loss of at least 50%, ongoing (6) or finished (8)
EIGHT_CONNECTED = np.ones((3, 3))
# A pixel is confirmed weeks or months after the date it is first seen, and drops out of the product
# about a year after that, so one reading undercounts both ends of a 12-month window. Readings on the
# window end and on the same day 2 and 4 months later together settle to within about 5% (spike log
# section 13). Whole months keep each granule shared between neighbouring points.
SETTLE_OFFSETS_MONTHS = (0, 2, 4)


def decode_date(days: int) -> dt.date:
    return EPOCH + dt.timedelta(days=int(days))


def loss_mask(status: np.ndarray, date: np.ndarray, window_end: dt.date, days: int = 365) -> np.ndarray:
    end = (window_end - EPOCH).days
    return np.isin(status, CONFIRMED_HEAVY_LOSS) & (date > end - days) & (date <= end)


def reading_days(window_end: dt.date, today: dt.date) -> tuple[list[dt.date], bool]:
    def add(months):
        m = window_end.month - 1 + months
        return window_end.replace(year=window_end.year + m // 12, month=m % 12 + 1)

    days = [add(m) for m in SETTLE_OFFSETS_MONTHS]
    passed = [d for d in days if d <= today]
    return passed, len(passed) == len(days)


def window_mask(readings, window_end: dt.date, days: int = 365):
    """Pixels that any reading shows as heavy loss first seen inside the window, with that first-seen date."""
    mask = np.zeros(readings[0][0].shape, bool)
    date = np.zeros(readings[0][1].shape, np.int32)
    for status, d in readings:
        m = loss_mask(status, d, window_end, days)
        date = np.where(m & ~mask, d, date)
        mask |= m
    return mask, date


def cluster_polygons(mask, date, transform, crs, min_ha=1.0) -> gpd.GeoDataFrame:
    pixel_ha = abs(transform.a * transform.e) / 1e4
    labels, n = ndimage.label(mask, structure=EIGHT_CONNECTED)
    sizes = ndimage.sum(mask, labels, range(1, n + 1)) * pixel_ha
    keep = np.flatnonzero(sizes >= min_ha - 1e-9) + 1
    if not len(keep):
        return gpd.GeoDataFrame(columns=["local_id", "ha", "first_seen", "last_seen", "geometry"], geometry="geometry", crs=crs)
    first = ndimage.minimum(date, labels, keep)
    last = ndimage.maximum(date, labels, keep)
    kept = np.where(np.isin(labels, keep), labels, 0).astype("int32")
    parts: dict[int, list] = {}
    for geom, value in shapes(kept, mask=kept > 0, transform=transform, connectivity=8):
        parts.setdefault(int(value), []).append(shape(geom))
    rows = [{"ha": round(float(sizes[k - 1]), 2), "first_seen": str(decode_date(first[i])),
             "last_seen": str(decode_date(last[i])), "geometry": unary_union(parts[k])}
            for i, k in enumerate(keep)]
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=crs).sort_values("ha", ascending=False, kind="stable")
    gdf = gdf.reset_index(drop=True)
    gdf.insert(0, "local_id", gdf.index + 1)
    return gdf
