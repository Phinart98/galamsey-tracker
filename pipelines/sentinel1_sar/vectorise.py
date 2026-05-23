"""Vectorise the change mask raster into polygon rows in alerts_sar.

Pattern mirrors pipelines/gfw_alerts/ingest.py:
  1. rasterio.features.shapes() over the mask band
  2. shapely simplify + area filter + UTM->WGS84 reproject
  3. Compute per-polygon delta_db_mean, delta_db_max, area_ha, confidence
  4. UNLOGGED staging table + COPY + INSERT ... ON CONFLICT DO NOTHING
  5. sar_alerts_join_admin(run_id) populates region/district/reserve/concession FKs

alert_uid = md5(detection_period_start:wkb_sha) -- same period+geom produces
the same UID, making re-runs idempotent.
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import psycopg
import rasterio
import structlog
from pyproj import Transformer
from rasterio.features import geometry_mask, shapes
from shapely.geometry import Polygon, shape
from shapely.ops import transform as shp_transform

log = structlog.get_logger()

STAGING_DDL = """
-- TEMP table is session-scoped: invisible to other sessions and dropped
-- automatically when the connection closes. Eliminates the cross-session
-- race that an UNLOGGED shared table would have between two concurrent
-- pipeline runs (e.g. operator-triggered workflow_dispatch overlapping
-- the scheduled monthly cron).
CREATE TEMPORARY TABLE IF NOT EXISTS alerts_sar_staging (
    alert_uid              TEXT,
    detection_period_start DATE,
    detection_period_end   DATE,
    area_ha                NUMERIC,
    delta_db_mean          NUMERIC,
    delta_db_max           NUMERIC,
    confidence             TEXT,
    cog_url                TEXT,
    stac_item_id           TEXT,
    geom_wkt               TEXT
) ON COMMIT DROP;
"""

UPSERT_SQL = """
INSERT INTO alerts_sar (
    alert_uid, detection_period_start, detection_period_end,
    area_ha, delta_db_mean, delta_db_max, confidence,
    cog_url, stac_item_id, geom, pipeline_run_id
)
SELECT
    alert_uid,
    detection_period_start,
    detection_period_end,
    area_ha,
    delta_db_mean,
    delta_db_max,
    confidence,
    cog_url,
    stac_item_id,
    ST_Multi(ST_SetSRID(ST_GeomFromText(geom_wkt), 4326)),
    %(run_id)s
FROM alerts_sar_staging
-- On re-run, bump pipeline_run_id so sar_alerts_join_admin re-evaluates
-- region/district/forest_reserve/concession FKs against the current
-- boundaries tables -- otherwise newly-added forest reserves (etc.) would
-- never associate with previously-detected polygons. Geometry/area/dates
-- are immutable for a given alert_uid (md5(period:wkb_sha)) so we don't
-- update those.
ON CONFLICT (alert_uid) DO UPDATE
SET pipeline_run_id = EXCLUDED.pipeline_run_id,
    cog_url         = EXCLUDED.cog_url,
    stac_item_id    = EXCLUDED.stac_item_id;
"""

COPY_COLS = [
    "alert_uid",
    "detection_period_start",
    "detection_period_end",
    "area_ha",
    "delta_db_mean",
    "delta_db_max",
    "confidence",
    "cog_url",
    "stac_item_id",
    "geom_wkt",
]


def _make_uid(period_start: date, geom_wkb: bytes) -> str:
    """alert_uid = md5(YYYY-MM-DD:sha256(wkb)[:16]).

    Truncating the inner sha keeps the UID short while preserving enough
    bits that geometric collisions across a month are negligible.
    """
    geom_digest = hashlib.sha256(geom_wkb).hexdigest()[:16]
    return hashlib.md5(f"{period_start.isoformat()}:{geom_digest}".encode()).hexdigest()


def _classify_confidence(
    area_ha: float, delta_db_mean: float, near_water: bool, in_reserve: bool
) -> str:
    """Return 'low' | 'medium' | 'high' per the Forkuor-adapted rules.

    high   -> near water OR in forest reserve (the canonical galamsey signal)
    low    -> very small or very weak detection (kept for completeness, not
              shown by default on the dashboard)
    medium -> everything else
    """
    if area_ha < 1.0 or delta_db_mean < 2.0:
        return "low"
    if near_water or in_reserve:
        return "high"
    return "medium"


def _iter_features(
    cog_path: Path,
    min_area_m2: float,
) -> Iterator[tuple[Polygon, dict[str, Any]]]:
    """Yield (polygon_in_native_crs, {delta_vv_mean, delta_vh_mean, area_m2}).

    The COG is 3-band float32: band 1 delta_vv, band 2 delta_vh, band 3 mask.
    We polygonise the mask, then sample each delta band INSIDE the polygon
    (rasterio masks by geometry) to compute per-polygon stats.
    """
    with rasterio.open(cog_path) as src:
        delta_vv = src.read(1)
        delta_vh = src.read(2)
        mask_band = src.read(3).astype("uint8")
        transform = src.transform

        for geom_dict, value in shapes(
            mask_band, mask=(mask_band == 1), transform=transform
        ):
            if value != 1:
                continue
            poly = shape(geom_dict)
            if not isinstance(poly, Polygon):
                continue
            # Drop tiny features (Sentinel-1 speckle). Area in native CRS (m²
            # because UTM zone 30N projection).
            if poly.area < min_area_m2:
                continue
            poly_simple = poly.simplify(50.0, preserve_topology=True)
            if poly_simple.is_empty or not poly_simple.is_valid:
                continue
            # Sample the underlying delta values inside the polygon by
            # building a per-polygon boolean mask against the full raster
            # extent. Cost is O(raster_pixels * n_polygons) -- acceptable for
            # ~500 polygons over a hotspot AOI, but is the planned next
            # optimisation if polygon counts grow past 5k (windowed read).
            window_mask = geometry_mask(
                [poly_simple],
                out_shape=delta_vv.shape,
                transform=transform,
                invert=True,
            )
            vv_inside = delta_vv[window_mask]
            vh_inside = delta_vh[window_mask]
            finite_vv = vv_inside[np.isfinite(vv_inside)]
            finite_vh = vh_inside[np.isfinite(vh_inside)]
            if finite_vv.size == 0 or finite_vh.size == 0:
                continue
            # delta_db_mean is the average of the two polarisations' per-pixel
            # means within the polygon. The column name matches what it
            # computes -- the earlier `min(...)` was a stricter signal but
            # misled downstream consumers reading the column name.
            stats = {
                "delta_db_mean": float((finite_vv.mean() + finite_vh.mean()) / 2.0),
                "delta_db_max": float(max(finite_vv.max(), finite_vh.max())),
                "area_m2": float(poly_simple.area),
            }
            yield poly_simple, stats


def _classify_near_water_in_reserve(
    conn: psycopg.Connection,
    geom_wkt: str,
) -> tuple[bool, bool]:
    """Query PostGIS for water-proximity (<=500 m) and forest-reserve containment.

    water_bodies + forest_reserves are seeded in migration 0002 (boundaries).
    The query runs per polygon -- bounded by the index, this is microseconds.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH g AS (
                SELECT ST_GeomFromText(%(wkt)s, 4326) AS geom
            )
            SELECT
                EXISTS (
                    SELECT 1 FROM water_bodies w, g
                    WHERE ST_DWithin(g.geom::geography, w.geom::geography, 500)
                ) AS near_water,
                EXISTS (
                    SELECT 1 FROM forest_reserves r, g
                    WHERE ST_Intersects(g.geom, r.geom)
                ) AS in_reserve
            """,
            {"wkt": geom_wkt},
        )
        row = cur.fetchone()
    assert row is not None
    return bool(row[0]), bool(row[1])


def vectorise_and_load(
    cog_path: Path,
    period_start: date,
    period_end: date,
    cog_url: str,
    stac_item_id: str,
    pipeline_run_id: int | None,
    database_url: str | None,
    min_area_m2: float,
    dry_run: bool,
) -> dict[str, int]:
    """Polygonise the COG mask, classify, COPY+INSERT into alerts_sar.

    Returns counts: {candidates, after_area_filter, after_dedup, inserted}.
    """
    # Native CRS for area math is UTM (m²); for storage we reproject to 4326.
    project_to_4326 = Transformer.from_crs(32630, 4326, always_xy=True).transform

    rows_buf = io.StringIO()
    writer = csv.writer(rows_buf)
    candidates = 0
    written = 0

    # `with psycopg.connect(...)` is the canonical context manager: it
    # rolls back on exception and closes the connection cleanly. The earlier
    # try/finally with only .close() would leak open transactions on error
    # (psycopg3 default autocommit=False). conn is None during dry-run so we
    # branch around it.
    conn: psycopg.Connection | None = None
    if not dry_run and database_url:
        conn = psycopg.connect(database_url)

    try:
        seen_uids: set[str] = set()
        for poly_utm, stats in _iter_features(cog_path, min_area_m2):
            candidates += 1
            poly_4326 = shp_transform(project_to_4326, poly_utm)
            geom_wkt = poly_4326.wkt
            geom_wkb = poly_4326.wkb
            uid = _make_uid(period_start, geom_wkb)
            if uid in seen_uids:
                continue
            seen_uids.add(uid)

            area_ha = stats["area_m2"] / 10_000.0

            if conn is not None:
                near_water, in_reserve = _classify_near_water_in_reserve(conn, geom_wkt)
            else:
                near_water, in_reserve = False, False

            confidence = _classify_confidence(
                area_ha, stats["delta_db_mean"], near_water, in_reserve
            )

            writer.writerow([
                uid,
                period_start.isoformat(),
                period_end.isoformat(),
                f"{area_ha:.4f}",
                f"{stats['delta_db_mean']:.4f}",
                f"{stats['delta_db_max']:.4f}",
                confidence,
                cog_url,
                stac_item_id,
                geom_wkt,
            ])
            written += 1

        log.info(
            "Vectorisation done",
            candidates=candidates,
            after_area_filter=written,
            min_area_m2=min_area_m2,
        )

        if dry_run or conn is None:
            rows_buf.seek(0)
            for line in list(rows_buf)[:3]:
                print(line, end="")
            return {
                "candidates": candidates,
                "after_area_filter": written,
                "after_dedup": written,
                "inserted": 0,
            }

        with conn.cursor() as cur:
            cur.execute(STAGING_DDL)
            rows_buf.seek(0)
            copy_sql = (
                f"COPY alerts_sar_staging ({','.join(COPY_COLS)}) "
                "FROM STDIN WITH (FORMAT CSV)"
            )
            with cur.copy(copy_sql) as copy_obj:
                copy_obj.write(rows_buf.read())
            cur.execute(UPSERT_SQL, {"run_id": pipeline_run_id})
            inserted = cur.rowcount
            cur.execute("SELECT sar_alerts_join_admin(%s)", (pipeline_run_id,))
            # No explicit TRUNCATE needed: the TEMP TABLE has ON COMMIT DROP.
        conn.commit()

        log.info(
            "alerts_sar write complete",
            inserted=inserted,
            run_id=pipeline_run_id,
        )
        return {
            "candidates": candidates,
            "after_area_filter": written,
            "after_dedup": written,
            "inserted": inserted,
        }
    except Exception:
        # Roll back any in-flight transaction explicitly. Without this, the
        # finally's .close() leaves an implicit BEGIN open (psycopg3 default
        # autocommit=False), which on some drivers logs WARNING but more
        # importantly leaves the COPY+UPSERT half-applied as a snapshot
        # other sessions can read until the connection is GC'd.
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            conn.close()
