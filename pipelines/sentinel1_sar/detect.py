"""Sentinel-1 SAR change detection -- monthly ingest entrypoint.

Pipeline (mirrors pipelines/gfw_alerts/ingest.py structure):
  1. Open a pipeline_runs row before any heavy work.
  2. Query MPC sentinel-1-rtc for the baseline window and current period.
  3. Compute Forkuor 2020 delta + joint VV/VH threshold mask.
  4. Write a 3-band COG to a temp dir.
  5. Upload COG to R2 + append STAC Item to catalog.
  6. Vectorise mask, classify, COPY+INSERT into alerts_sar.
  7. Mark pipeline_runs row success/failed.

Designed to run on GitHub Actions ubuntu-latest (16 GB RAM) for full Ghana
in 60-120 minutes. Local runs against a single hotspot AOI complete in 5-10
minutes and don't need DATABASE_URL when --dry-run.
"""

from __future__ import annotations

import os

# GDAL HTTP auto-retry MUST be set before any rasterio / stackstac import:
# Azure Blob Storage (where MPC stores Sentinel-1 RTC COGs) occasionally
# returns partial responses under parallel load. Without retries, a single
# short read kills the whole compute. setdefault keeps user overrides.
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
os.environ.setdefault("CPL_VSIL_CURL_USE_HEAD", "NO")

import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import click
import psycopg
import structlog

from aoi import AOI_BBOX
from cog import upload_to_r2, write_cog
from stac_catalog import COG_KEY_TEMPLATE, append_item
from stac_query import query_scenes
from threshold import baseline_window, compute_delta
from vectorise import vectorise_and_load

log = structlog.get_logger()


def _previous_month(today: date) -> str:
    first_this_month = today.replace(day=1)
    last_of_prev = first_this_month - timedelta(days=1)
    return last_of_prev.strftime("%Y-%m")


def _period_range(period: str) -> tuple[date, date]:
    """Parse YYYY-MM into the (first-day-of-month, last-day-of-month) range."""
    year, month = period.split("-")
    start = date(int(year), int(month), 1)
    if start.month == 12:
        end = date(start.year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(start.year, start.month + 1, 1) - timedelta(days=1)
    return start, end


@click.command()
@click.option(
    "--period",
    default=None,
    help="Detection period YYYY-MM (default: previous calendar month)",
)
@click.option(
    "--aoi",
    type=click.Choice(["ghana", "wassa", "atewa", "birim", "tano", "pra"]),
    default="ghana",
    help="AOI bbox (smaller AOIs are for local testing)",
)
@click.option("--baseline-months", type=int, default=12, help="Trailing baseline months")
@click.option("--threshold-db", type=float, default=1.65, help="Backscatter delta threshold (dB)")
@click.option("--min-area-ha", type=float, default=0.5, help="Drop polygons below this area")
@click.option("--dry-run", is_flag=True, help="Compute everything but skip R2 + DB writes")
def main(
    period: str | None,
    aoi: str,
    baseline_months: int,
    threshold_db: float,
    min_area_ha: float,
    dry_run: bool,
) -> None:
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ]
    )

    period_str = period or _previous_month(date.today())
    period_start, period_end = _period_range(period_str)
    base_start, base_end = baseline_window(period_start, baseline_months)
    bbox = AOI_BBOX[aoi]  # type: ignore[index]
    min_area_m2 = min_area_ha * 10_000.0

    log.info(
        "Starting SAR detection",
        period=period_str,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        baseline_start=base_start.isoformat(),
        baseline_end=base_end.isoformat(),
        aoi=aoi,
        bbox=bbox,
        threshold_db=threshold_db,
        min_area_ha=min_area_ha,
        dry_run=dry_run,
    )

    database_url = os.environ.get("DATABASE_URL")
    if not database_url and not dry_run:
        raise click.ClickException("DATABASE_URL is required for non-dry-run mode")

    run_id: int | None = None
    if not dry_run and database_url:
        with psycopg.connect(database_url) as boot_conn:
            with boot_conn.cursor() as cur:
                # Precondition: alerts_sar must exist (migration 0006 applied).
                # If it doesn't, fail loudly BEFORE the 60-120 min compute
                # rather than after.
                cur.execute(
                    "SELECT to_regclass('public.alerts_sar') IS NOT NULL"
                )
                row = cur.fetchone()
                assert row is not None
                if not row[0]:
                    raise click.ClickException(
                        "alerts_sar table is missing; apply migrations 0006/0007 first"
                    )
                # Warn if confidence='high' is structurally unreachable: it
                # depends on water_bodies and forest_reserves being seeded.
                # An empty boundary table silently downgrades every polygon.
                cur.execute(
                    "SELECT "
                    "  (SELECT count(*) FROM water_bodies),"
                    "  (SELECT count(*) FROM forest_reserves)"
                )
                row = cur.fetchone()
                assert row is not None
                wb_count, fr_count = row
                if wb_count == 0 or fr_count == 0:
                    log.warning(
                        "Boundary tables are empty: confidence='high' "
                        "classification will be unreachable until they are "
                        "seeded; all detected polygons will be 'medium' or 'low'",
                        water_bodies=wb_count,
                        forest_reserves=fr_count,
                    )

                cur.execute(
                    "INSERT INTO pipeline_runs (pipeline_name, started_at, status) "
                    "VALUES ('sentinel1_sar', now(), 'running') RETURNING id"
                )
                row = cur.fetchone()
                assert row is not None
                run_id = row[0]
            boot_conn.commit()

    def mark_run(status: str, *, rows: int | None = None, notes: str | None = None) -> None:
        if run_id is None or not database_url:
            return
        with psycopg.connect(database_url) as c:
            with c.cursor() as cur:
                cur.execute(
                    "UPDATE pipeline_runs SET status=%s, finished_at=now(), "
                    "rows_inserted=%s, notes=%s WHERE id=%s",
                    (status, rows, notes, run_id),
                )
            c.commit()

    try:
        baseline_items = query_scenes(bbox, base_start, base_end)
        current_items = query_scenes(bbox, period_start, period_end)
        if not baseline_items or not current_items:
            note = (
                f"baseline_items={len(baseline_items)} current_items={len(current_items)} "
                "- no scenes; aborting"
            )
            log.warning("No scenes", baseline=len(baseline_items), current=len(current_items))
            mark_run("failed", notes=note)
            sys.exit(2)

        ds = compute_delta(baseline_items, current_items, bbox, threshold_db)

        with tempfile.TemporaryDirectory() as tmpdir:
            cog_local = Path(tmpdir) / f"{period_str}.tif"
            write_cog(ds, cog_local)

            if dry_run:
                # Inspect mask without R2/DB. Polygonisation runs in memory.
                stats = vectorise_and_load(
                    cog_local,
                    period_start,
                    period_end,
                    cog_url="dry-run://no-r2",
                    stac_item_id="dry-run",
                    pipeline_run_id=None,
                    database_url=None,
                    min_area_m2=min_area_m2,
                    dry_run=True,
                )
                log.info("Dry run complete", **stats)
                return

            cog_key = COG_KEY_TEMPLATE.format(period=period_str)
            cog_url = upload_to_r2(cog_local, cog_key)
            item_url = append_item(
                period_str,
                period_start,
                period_end,
                threshold_db,
                baseline_months,
                cog_url,
            )

            stats = vectorise_and_load(
                cog_local,
                period_start,
                period_end,
                cog_url=cog_url,
                stac_item_id=f"sentinel1-change-{period_str}",
                pipeline_run_id=run_id,
                database_url=database_url,
                min_area_m2=min_area_m2,
                dry_run=False,
            )
            # Sanity bound: Forkuor 2020 + 0.5 ha filter over Ghana should
            # produce hundreds of polygons per month, not tens of thousands.
            # If we cross 10k, something's wrong with the threshold or filter
            # and we'd rather fail loudly than silently pollute alerts_sar.
            if stats["after_area_filter"] > 10_000:
                msg = (
                    f"polygon_count={stats['after_area_filter']} exceeds sanity "
                    f"bound 10000 -- check threshold_db ({threshold_db}) and "
                    f"min_area_m2 ({min_area_m2})"
                )
                log.warning("Sanity bound exceeded", **stats)
                mark_run("failed", notes=msg)
                sys.exit(3)
            log.info("Run complete", item_url=item_url, **stats)
            mark_run("success", rows=stats["inserted"], notes=str(stats))

    except Exception as exc:
        log.exception("Pipeline failed", error=str(exc))
        mark_run("failed", notes=str(exc)[:1000])
        sys.exit(1)


if __name__ == "__main__":
    main()
