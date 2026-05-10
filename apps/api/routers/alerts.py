"""GFW alerts endpoints.

Mounted at prefix /alerts in main.py:
  GET /alerts                    -> GeoJSON FeatureCollection (filtered)
  GET /alerts/by-region          -> per-region per-day counts (sparkline data)
  GET /alerts/stats              -> totals + per-source counts (hero stats)
"""

from collections import defaultdict
from datetime import date, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from psycopg import AsyncConnection
from psycopg.rows import DictRow

from db import get_conn
from geo import rows_to_feature_collection
from schemas import AlertCollection, AlertsByRegionRow, AlertsStats, RegionDateCount

router = APIRouter()

MinConfidence = Literal["low", "high", "highest"]
ConnDep = Annotated[AsyncConnection[DictRow], Depends(get_conn)]
DateFromQuery = Annotated[date | None, Query(alias="from")]
DateToQuery = Annotated[date | None, Query()]
ConfidenceQuery = Annotated[MinConfidence, Query()]


def _confidence_filter(min_confidence: MinConfidence) -> str:
    # Values are constrained by the Literal type, so inlining as SQL is safe.
    if min_confidence == "highest":
        return "AND confidence = 'highest'"
    if min_confidence == "high":
        return "AND confidence IN ('high','highest')"
    return ""


def _default_window(
    from_: date | None, to: date | None, default_days: int = 30
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
async def list_alerts(
    *,
    conn: ConnDep,
    from_: DateFromQuery = None,
    to: DateToQuery = None,
    region: Annotated[str | None, Query()] = None,
    min_confidence: ConfidenceQuery = "low",
    limit: Annotated[int, Query(ge=1, le=25000)] = 5000,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    win_from, win_to = _default_window(from_, to)
    sql = f"""
        SELECT a.id,
               a.alert_date,
               a.source,
               a.confidence,
               a.region_id,
               a.district_id,
               a.forest_reserve_id,
               a.concession_id,
               ST_AsGeoJSON(a.geom) AS geom_geojson
        FROM alerts_gfw a
        LEFT JOIN regions r ON r.id = a.region_id
        WHERE a.alert_date BETWEEN %(from)s AND %(to)s
          {"AND r.name = %(region)s" if region else ""}
          {_confidence_filter(min_confidence)}
        ORDER BY a.alert_date DESC, a.id
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


@router.get("/by-region", response_model=list[AlertsByRegionRow])
async def alerts_by_region(
    *,
    conn: ConnDep,
    from_: DateFromQuery = None,
    to: DateToQuery = None,
    min_confidence: ConfidenceQuery = "low",
) -> list[AlertsByRegionRow]:
    win_from, win_to = _default_window(from_, to)
    sql = f"""
        WITH days AS (
            SELECT generate_series(%(from)s::date, %(to)s::date, '1 day')::date AS d
        ),
        region_days AS (
            SELECT r.id AS region_id, r.name AS region_name, days.d AS dt
            FROM regions r
            CROSS JOIN days
        ),
        counts AS (
            SELECT region_id, alert_date, COUNT(*)::int AS n
            FROM alerts_gfw
            WHERE alert_date BETWEEN %(from)s AND %(to)s
              AND region_id IS NOT NULL
              {_confidence_filter(min_confidence)}
            GROUP BY region_id, alert_date
        )
        SELECT rd.region_id,
               rd.region_name,
               rd.dt::text AS date,
               COALESCE(c.n, 0) AS count
        FROM region_days rd
        LEFT JOIN counts c
          ON c.region_id = rd.region_id AND c.alert_date = rd.dt
        ORDER BY rd.region_name, rd.dt
    """
    rows = await _fetch_dicts(conn, sql, {"from": win_from, "to": win_to})

    grouped: dict[int, dict[str, Any]] = {}
    for r in rows:
        bucket = grouped.setdefault(
            r["region_id"],
            {"region_id": r["region_id"], "region_name": r["region_name"], "dates": []},
        )
        bucket["dates"].append(RegionDateCount(date=r["date"], count=r["count"]))
    return [AlertsByRegionRow(**v) for v in grouped.values()]


@router.get("/stats", response_model=AlertsStats)
async def alerts_stats(
    *,
    conn: ConnDep,
    from_: DateFromQuery = None,
    to: DateToQuery = None,
) -> AlertsStats:
    win_from, win_to = _default_window(from_, to)
    sql = """
        SELECT
            COUNT(*)::int                                          AS total,
            COUNT(*) FILTER (WHERE confidence IN ('high','highest'))::int AS high_confidence,
            source,
            COUNT(*)::int                                          AS source_count
        FROM alerts_gfw
        WHERE alert_date BETWEEN %(from)s AND %(to)s
        GROUP BY GROUPING SETS ((), (source))
    """
    rows = await _fetch_dicts(conn, sql, {"from": win_from, "to": win_to})

    total = 0
    high = 0
    by_source: dict[str, int] = defaultdict(int)
    for r in rows:
        if r["source"] is None:
            total = r["total"]
            high = r["high_confidence"]
        else:
            by_source[r["source"]] = r["source_count"]
    return AlertsStats(total=total, high_confidence=high, by_source=dict(by_source))
