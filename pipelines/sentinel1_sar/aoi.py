"""AOI bounding boxes for the Sentinel-1 SAR pipeline.

The ghana bbox is the same closed polygon used by pipelines/gfw_alerts/ingest.py.
Hotspot bboxes are ~30 km buffers around the dashboard's HOTSPOTS centroids
(apps/web/composables/useSyntheticData.ts) for local testing.
"""

from typing import Literal

AOIKey = Literal["ghana", "wassa", "atewa", "birim", "tano", "pra"]

# (west, south, east, north) in WGS84 degrees.
AOI_BBOX: dict[AOIKey, tuple[float, float, float, float]] = {
    "ghana": (-3.26, 4.74, 1.20, 11.18),
    # ~30 km half-side buffers around the dashboard hotspot centroids.
    "wassa": (-2.35, 5.05, -1.75, 5.65),
    "atewa": (-0.85, 5.90, -0.25, 6.50),
    "birim": (-1.35, 6.05, -0.75, 6.65),
    "tano":  (-2.80, 6.85, -2.20, 7.45),
    "pra":   (-1.90, 5.40, -1.30, 6.00),
}
