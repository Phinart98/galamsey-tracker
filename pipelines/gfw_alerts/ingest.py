"""Weekly ingest of GFW integrated deforestation alerts for Ghana.

Workflow (mirrors pipelines/concessions/scrape.py):
  1. Open a pipeline_runs record before any HTTP work (committed immediately
     for audit visibility even if the fetch crashes).
  2. Page through the GFW Data API SQL /query/json endpoint for the
     gfw_integrated_alerts dataset, filtered to Ghana bbox + date window.
  3. Normalise each row, compute alert_uid = md5(source:lon:lat:date), buffer
     into a CSV-shaped StringIO.
  4. CREATE/TRUNCATE UNLOGGED alerts_gfw_staging; COPY rows from buffer.
  5. INSERT INTO alerts_gfw ... ON CONFLICT (alert_uid) DO NOTHING (alerts are
     append-only events; re-runs are idempotent).
  6. SELECT alerts_gfw_join_admin(run_id) to populate region/district/reserve/
     concession FKs in one scoped UPDATE.
  7. TRUNCATE staging; mark pipeline_runs row success or failed.
"""

import csv
import hashlib
import io
import os
import sys
import time
from collections.abc import Iterator
from datetime import date, datetime, timedelta

import click
import httpx
import psycopg
import structlog

log = structlog.get_logger()

GFW_DATASET = "gfw_integrated_alerts"
GFW_VERSION = "latest"
GFW_QUERY_URL = (
    f"https://data-api.globalforestwatch.org/dataset/{GFW_DATASET}/{GFW_VERSION}/query/json"
)

# GFW raster query API requires a GeoJSON geometry, not bbox SQL.
# Ghana bbox as a closed polygon: SW, SE, NE, NW, SW.
GHANA_BBOX_GEOM = {
    "type": "Polygon",
    "coordinates": [[
        [-3.26, 4.74], [1.20, 4.74], [1.20, 11.18], [-3.26, 11.18], [-3.26, 4.74]
    ]],
}

# GFW publishes a single integrated `confidence` field with values
# {nominal, high, highest}. We accept `low` as a fallback for any future
# extension; the table CHECK constraint covers all four.
_VALID_CONFIDENCE = {"low", "high", "highest", "nominal"}

# The integrated dataset has NO per-source field. Detector provenance is
# implicit in the confidence value: 'highest' means detected by 2+ systems.
# Migration 0004 widens the source CHECK to allow 'integrated'.
_SOURCE_INTEGRATED = "integrated"

STAGING_DDL = """
CREATE UNLOGGED TABLE IF NOT EXISTS alerts_gfw_staging (
    alert_uid  TEXT,
    alert_date DATE,
    source     TEXT,
    confidence TEXT,
    lon        DOUBLE PRECISION,
    lat        DOUBLE PRECISION
);
TRUNCATE alerts_gfw_staging;
"""

UPSERT_SQL = """
INSERT INTO alerts_gfw (alert_uid, alert_date, source, confidence, geom, pipeline_run_id)
SELECT
    alert_uid,
    alert_date,
    source,
    confidence,
    ST_SetSRID(ST_MakePoint(lon, lat), 4326),
    %(run_id)s
FROM alerts_gfw_staging
ON CONFLICT (alert_uid) DO NOTHING;
"""

COPY_COLS = ["alert_uid", "alert_date", "source", "confidence", "lon", "lat"]


def make_uid(source: str, lon: float, lat: float, alert_date: date) -> str:
    # Round to 5 decimals (~1 m) so floating-point jitter in the API response
    # doesn't fragment dedup. Mirrors concessions.make_uid pattern.
    return hashlib.md5(
        f"{source}:{round(lon, 5)}:{round(lat, 5)}:{alert_date.isoformat()}".encode()
    ).hexdigest()


def parse_alert_date(raw: object) -> date | None:
    if isinstance(raw, date):
        return raw
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw).strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def normalise_confidence(raw: object) -> str | None:
    if not raw:
        return None
    s = str(raw).strip().lower()
    return s if s in _VALID_CONFIDENCE else None


def fetch_page(
    client: httpx.Client,
    page_no: int,
    date_from: date,
    date_to: date,
) -> list[dict[str, object]]:
    """Return rows from the GFW raster /query/json endpoint for one page.

    The integrated_alerts dataset is a RASTER tile set; the API requires
    POST with a geometry parameter (verified live against the API May 2026,
    not the misleading hint in the public dataset metadata page).

    Pagination: GFW's raster query endpoint does NOT support page params; it
    returns every alert pixel intersecting the geometry in one response.
    page_no is accepted so the iter_alerts loop reads naturally; only
    page_no=1 returns data.
    """
    if page_no > 1:
        return []
    body_payload = {
        "sql": (
            "SELECT latitude, longitude, "
            "gfw_integrated_alerts__date, "
            "gfw_integrated_alerts__confidence "
            "FROM results "
            f"WHERE gfw_integrated_alerts__date >= '{date_from.isoformat()}' "
            f"AND gfw_integrated_alerts__date <= '{date_to.isoformat()}'"
        ),
        "geometry": GHANA_BBOX_GEOM,
    }
    r = client.post(GFW_QUERY_URL, json=body_payload, timeout=180)
    r.raise_for_status()
    body = r.json()
    if isinstance(body, dict):
        data = body.get("data")
        if isinstance(data, list):
            return data
    return []


def iter_alerts(
    client: httpx.Client,
    date_from: date,
    date_to: date,
    max_pages: int | None,
) -> Iterator[dict[str, object]]:
    page = 1
    while True:
        if max_pages is not None and page > max_pages:
            log.info("Max pages reached", max_pages=max_pages)
            break
        rows = fetch_page(client, page, date_from, date_to)
        if not rows:
            log.info("Pagination exhausted", last_page=page - 1)
            break
        log.info("Fetched page", page=page, rows=len(rows))
        yield from rows
        page += 1
        # Courtesy delay: GFW rate limits are undocumented but observed near
        # ~120 req/min on free keys; one half-second sleep keeps us comfortably below.
        time.sleep(0.5)


def normalise(raw: dict[str, object]) -> dict[str, object] | None:
    """Coerce a raw GFW row into the staging schema; return None to skip.

    The integrated dataset returns rows shaped as:
      {latitude, longitude, gfw_integrated_alerts__date, gfw_integrated_alerts__confidence}
    """
    lon = raw.get("longitude")
    lat = raw.get("latitude")
    if lon is None or lat is None:
        return None
    try:
        lon_f = float(str(lon))
        lat_f = float(str(lat))
    except (TypeError, ValueError):
        return None

    alert_date = parse_alert_date(raw.get("gfw_integrated_alerts__date"))
    if alert_date is None:
        return None

    confidence = normalise_confidence(raw.get("gfw_integrated_alerts__confidence"))
    if confidence is None:
        return None

    return {
        "alert_uid": make_uid(_SOURCE_INTEGRATED, lon_f, lat_f, alert_date),
        "alert_date": alert_date.isoformat(),
        "source": _SOURCE_INTEGRATED,
        "confidence": confidence,
        "lon": lon_f,
        "lat": lat_f,
    }


@click.command()
@click.option(
    "--from",
    "from_date",
    default=None,
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Window start (YYYY-MM-DD); default = today - 14 days",
)
@click.option(
    "--to",
    "to_date",
    default=None,
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Window end (YYYY-MM-DD); default = today",
)
@click.option("--max-pages", default=None, type=int, help="Stop after N pages")
@click.option("--dry-run", is_flag=True, help="Fetch and normalise but skip database writes")
def main(
    from_date: datetime | None,
    to_date: datetime | None,
    max_pages: int | None,
    dry_run: bool,
) -> None:
    """Fetch GFW integrated alerts for Ghana and upsert into alerts_gfw."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ]
    )

    today = date.today()
    win_to = to_date.date() if to_date else today
    win_from = from_date.date() if from_date else today - timedelta(days=14)

    if win_from > win_to:
        raise click.ClickException(f"--from {win_from} is after --to {win_to}")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url and not dry_run:
        raise click.ClickException("DATABASE_URL environment variable is required")

    api_key = os.environ.get("GFW_API_KEY")
    if not api_key and not dry_run:
        raise click.ClickException("GFW_API_KEY environment variable is required")

    headers = {
        "User-Agent": "galamsey-tracker/1.0 (+https://github.com/Phinart98/galamsey-tracker)",
    }
    if api_key:
        headers["x-api-key"] = api_key

    log.info(
        "Starting ingest",
        date_from=win_from.isoformat(),
        date_to=win_to.isoformat(),
        max_pages=max_pages,
        dry_run=dry_run,
    )

    run_id: int | None = None
    if not dry_run and database_url:
        with psycopg.connect(database_url) as boot_conn:
            with boot_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO pipeline_runs (pipeline_name, started_at, status) "
                    "VALUES ('gfw_alerts', now(), 'running') RETURNING id"
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

    rows_buf = io.StringIO()
    writer = csv.writer(rows_buf)
    total = 0
    skipped = 0

    try:
        # follow_redirects=True is required: GFW serves /latest as a 307 to a
        # versioned URL (e.g. /v20260509). httpx blocks POST->POST redirects
        # by default because they re-submit the body; here that's exactly
        # what we want.
        with httpx.Client(headers=headers, follow_redirects=True) as client:
            for raw in iter_alerts(client, win_from, win_to, max_pages):
                normed = normalise(raw)
                if normed is None:
                    skipped += 1
                    continue
                writer.writerow([normed[c] for c in COPY_COLS])
                total += 1
    except Exception as exc:
        log.error("HTTP fetch failed", error=str(exc))
        mark_run("failed", notes=str(exc)[:1000])
        sys.exit(1)

    log.info("Fetch done", rows=total, skipped=skipped)

    if dry_run:
        rows_buf.seek(0)
        sample = list(rows_buf)[:3]
        for line in sample:
            print(line, end="")
        return

    if total == 0:
        log.warning("No valid rows fetched -- nothing written")
        mark_run("success", rows=0)
        return

    assert database_url is not None
    with psycopg.connect(database_url) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(STAGING_DDL)

                rows_buf.seek(0)
                copy_sql = (
                    f"COPY alerts_gfw_staging ({','.join(COPY_COLS)}) "
                    "FROM STDIN WITH (FORMAT CSV)"
                )
                with cur.copy(copy_sql) as copy_obj:
                    copy_obj.write(rows_buf.read())

                cur.execute(UPSERT_SQL, {"run_id": run_id})
                inserted = cur.rowcount

                cur.execute("SELECT alerts_gfw_join_admin(%s)", (run_id,))

                cur.execute("TRUNCATE alerts_gfw_staging")
            conn.commit()
            mark_run("success", rows=inserted)
            log.info("Write complete", inserted=inserted, run_id=run_id)

        except Exception as exc:
            conn.rollback()
            mark_run("failed", notes=str(exc)[:1000])
            log.error("Pipeline failed", error=str(exc), run_id=run_id)
            sys.exit(1)


if __name__ == "__main__":
    main()
