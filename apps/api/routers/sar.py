"""Sentinel-1 SAR alerts endpoints.

Mounted at prefix /sar in main.py:
  GET /sar         -> GeoJSON FeatureCollection (filtered by date + confidence)
  GET /sar/stats   -> totals + per-region area + per-confidence counts
"""

from datetime import date, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from psycopg import AsyncConnection
from psycopg.rows import DictRow

from db import get_conn
from geo import rows_to_feature_collection
from schemas import AlertCollection, SarStats, SarStatsRegion

router = APIRouter()

MinConfidence = Literal["low", "medium", "high"]
ConnDep = Annotated[AsyncConnection[DictRow], Depends(get_conn)]
DateFromQuery = Annotated[date | None, Query(alias="from")]
DateToQuery = Annotated[date | None, Query()]
ConfidenceQuery = Annotated[MinConfidence, Query()]


def _confidence_filter(min_confidence: MinConfidence) -> str:
    # Literal-typed input is safe to inline.
    if min_confidence == "high":
        return "AND confidence = 'high'"
    if min_confidence == "medium":
        return "AND confidence IN ('medium','high')"
    return ""


def _default_window(
    from_: date | None, to: date | None, default_days: int = 60
) -> tuple[date, date]:
    win_to = to or date.today()
    win_from = from_ or win_to - timedelta(days=default_days)
    return win_from, win_to


async def _fetch_dicts(
    conn: AsyncConnection[DictRow], sql: str, params: dict[str, Any]
) -> list[dict[str, Any]]:
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()


@router.get("", response_model=AlertCollection)
async def list_sar(
    *,
    conn: ConnDep,
    from_: DateFromQuery = None,
    to: DateToQuery = None,
    region: Annotated[str | None, Query()] = None,
    min_confidence: ConfidenceQuery = "medium",
    limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    win_from, win_to = _default_window(from_, to)
    # region filter uses a subquery so the LEFT JOIN above stays free to
    # surface unassigned rows; a direct `r.name = ...` predicate would
    # silently drop NULL-region rows (LEFT JOIN -> effectively INNER JOIN
    # for any caller filtering by region), inconsistent with /sar/stats's
    # "(unassigned)" bucket.
    sql = f"""
        SELECT a.id,
               a.detection_period_start,
               a.detection_period_end,
               a.area_ha,
               a.delta_db_mean,
               a.delta_db_max,
               a.confidence,
               a.region_id,
               a.district_id,
               a.forest_reserve_id,
               a.concession_id,
               a.cog_url,
               a.stac_item_id,
               ST_AsGeoJSON(a.geom) AS geom_geojson
        FROM alerts_sar a
        WHERE a.detection_period_start BETWEEN %(from)s AND %(to)s
          {
            "AND a.region_id = (SELECT id FROM regions WHERE name = %(region)s LIMIT 1)"
            if region else ""
          }
          {_confidence_filter(min_confidence)}
        ORDER BY a.detection_period_start DESC, a.area_ha DESC, a.id
        LIMIT %(limit)s OFFSET %(offset)s
    """
    params: dict[str, Any] = {
        "from": win_from,
        "to": win_to,
        "limit": limit,
        "offset": offset,
    }
    if region:
        params["region"] = region
    rows = await _fetch_dicts(conn, sql, params)

    fc = rows_to_feature_collection(rows)
    fc["next_offset"] = offset + limit if len(rows) == limit else None
    return fc


@router.get("/stats", response_model=SarStats)
async def sar_stats(
    *,
    conn: ConnDep,
    from_: DateFromQuery = None,
    to: DateToQuery = None,
) -> SarStats:
    win_from, win_to = _default_window(from_, to)

    totals_sql = """
        SELECT
            COUNT(*)::int                                          AS total,
            COALESCE(SUM(area_ha), 0)::float                       AS total_area_ha,
            confidence
        FROM alerts_sar
        WHERE detection_period_start BETWEEN %(from)s AND %(to)s
        GROUP BY GROUPING SETS ((), (confidence))
    """
    totals = await _fetch_dicts(conn, totals_sql, {"from": win_from, "to": win_to})

    total = 0
    total_area_ha = 0.0
    by_confidence: dict[str, int] = {}
    for r in totals:
        if r["confidence"] is None:
            total = r["total"]
            total_area_ha = float(r["total_area_ha"])
        else:
            by_confidence[r["confidence"]] = r["total"]

    # LEFT JOIN so polygons whose sar_alerts_join_admin couldn't match a region
    # (e.g. just outside any boundary, or admin enrichment hasn't finished
    # yet) still show up. They land in an explicit '(unassigned)' bucket so
    # sum(by_region.polygon_count) == total — without this the totals_sql
    # block above would count them in `total` but the per-region breakdown
    # would silently drop them, leaving a UI mystery.
    by_region_sql = """
        SELECT a.region_id,
               COALESCE(r.name, '(unassigned)')   AS region_name,
               COUNT(*)::int                       AS polygon_count,
               COALESCE(SUM(a.area_ha), 0)::float  AS total_area_ha
        FROM alerts_sar a
        LEFT JOIN regions r ON r.id = a.region_id
        WHERE a.detection_period_start BETWEEN %(from)s AND %(to)s
        GROUP BY a.region_id, r.name
        ORDER BY total_area_ha DESC
    """
    by_region_rows = await _fetch_dicts(
        conn, by_region_sql, {"from": win_from, "to": win_to}
    )
    by_region = [SarStatsRegion(**r) for r in by_region_rows]

    return SarStats(
        total=total,
        by_confidence=by_confidence,
        by_region=by_region,
        total_area_ha=total_area_ha,
    )
