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
