"""Pydantic response models for the alerts router.

Kept intentionally thin: GeoJSON FeatureCollections are defined as plain dicts
because pydantic-modelling every nested geometry adds runtime cost without
buying type safety the spec already provides.
"""

from typing import Any

from pydantic import BaseModel


class RegionDateCount(BaseModel):
    date: str
    count: int


class AlertsByRegionRow(BaseModel):
    region_id: int
    region_name: str
    dates: list[RegionDateCount]


class AlertsStats(BaseModel):
    total: int
    high_confidence: int
    by_source: dict[str, int]


class AlertCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[dict[str, Any]]
    next_offset: int | None = None


class SarStatsRegion(BaseModel):
    # region_id is nullable because the per-region rollup uses a LEFT JOIN
    # so polygons whose admin enrichment didn't match a region still surface
    # as an "(unassigned)" bucket — see routers/sar.py sar_stats.
    region_id: int | None = None
    region_name: str
    polygon_count: int
    total_area_ha: float


class SarStats(BaseModel):
    total: int
    by_confidence: dict[str, int]
    by_region: list[SarStatsRegion]
    total_area_ha: float
