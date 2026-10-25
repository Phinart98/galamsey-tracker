"""Vectorise DIST-ALERT-HLS clusters into polygons with size and dates.

Rule (same as hotspots.py): confirmed loss of at least 50% (VEG-DIST-STATUS 6 or 8)
first detected within the last 365 days of the granule, 8-connected, at least 1 ha.
"""
import datetime as dt
import sys

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import shapes
from scipy import ndimage
from shapely.geometry import shape

EPOCH = dt.date(2020, 12, 31)  # VEG-DIST-DATE counts days from here
PIXEL_HA = 0.09                # 30 m pixels
MIN_HA = 1.0


def load_clusters(status_path="data/dist/VEG-DIST-STATUS.tif", date_path="data/dist/VEG-DIST-DATE.tif"):
    with rasterio.open(status_path) as s:
        status, transform, crs = s.read(1), s.transform, s.crs
    with rasterio.open(date_path) as s:
        date = s.read(1).astype(int)
    latest = int(date.max())
    recent = np.isin(status, [6, 8]) & (date >= latest - 365)
    labels, n = ndimage.label(recent, structure=np.ones((3, 3)))
    sizes = ndimage.sum(recent, labels, range(1, n + 1)) * PIXEL_HA
    keep = np.flatnonzero(sizes >= MIN_HA) + 1
    first = ndimage.minimum(date, labels, keep)
    last = ndimage.maximum(date, labels, keep)
    meta = {k: (sizes[k - 1], first[i], last[i]) for i, k in enumerate(keep)}

    kept = np.where(np.isin(labels, keep), labels, 0).astype("int32")
    geoms = {}
    for geom, value in shapes(kept, mask=kept > 0, transform=transform, connectivity=8):
        geoms.setdefault(int(value), []).append(shape(geom))
    rows = []
    for k, parts in geoms.items():
        ha, d0, d1 = meta[k]
        rows.append({
            "ha": round(float(ha), 2),
            "first_seen": str(EPOCH + dt.timedelta(int(d0))),
            "last_seen": str(EPOCH + dt.timedelta(int(d1))),
            "geometry": gpd.GeoSeries(parts).union_all(),
        })
    gdf = gpd.GeoDataFrame(rows, crs=crs).sort_values("ha", ascending=False).reset_index(drop=True)
    gdf["id"] = gdf.index + 1
    return gdf, str(EPOCH + dt.timedelta(latest))


if __name__ == "__main__":
    gdf, data_date = load_clusters()
    out = sys.argv[1] if len(sys.argv) > 1 else "data/clusters_30NXM.gpkg"
    gdf.to_file(out)
    print(f"{len(gdf)} clusters, {gdf.ha.sum():,.0f} ha, data up to {data_date} -> {out}")
    print(gdf.head(5)[["id", "ha", "first_seen", "last_seen"]].to_string(index=False))
