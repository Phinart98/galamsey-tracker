"""Concessions scraper for the Minerals Commission cadastre (ghana.revenuedev.org).

Workflow:
  1. Open a pipeline_runs record (committed immediately for audit visibility).
  2. Fetch pages from the JSON API; fall back to HTML card parsing if unavailable.
  3. Normalise + write rows into an UNLOGGED staging table via COPY.
  4. UPSERT from staging into concessions (ON CONFLICT updates status + last_seen_at).
  5. TRUNCATE staging; mark pipeline_runs row success or failure.
"""

import csv
import hashlib
import io
import json
import os
import sys
from datetime import date, datetime
from typing import Iterator

import click
import httpx
import psycopg
import structlog
from selectolax.parser import HTMLParser

log = structlog.get_logger()

BASE_URL = "https://ghana.revenuedev.org"
SOURCE_URL = BASE_URL + "/license"

# Verify this endpoint by opening DevTools > Network while browsing SOURCE_URL.
# Common patterns: /api/licenses?page=N&size=200 or /api/license/list?page=N
API_ENDPOINT = BASE_URL + "/api/licenses"

STAGING_DDL = """
CREATE UNLOGGED TABLE IF NOT EXISTS concessions_staging (
    cadastre_uid   TEXT,
    holder_name    TEXT,
    license_no     TEXT,
    license_type   TEXT,
    license_status TEXT,
    commodity      TEXT,
    granted_at     TEXT,
    expires_at     TEXT,
    geom_wkt       TEXT,
    source_url     TEXT
);
TRUNCATE concessions_staging;
"""

UPSERT_SQL = """
INSERT INTO concessions (
    cadastre_uid, holder_name, license_no, license_type, license_status,
    commodity, granted_at, expires_at, last_seen_at, pipeline_run_id, geom, source_url
)
SELECT
    cadastre_uid,
    holder_name,
    NULLIF(license_no, ''),
    NULLIF(license_type, ''),
    NULLIF(license_status, ''),
    NULLIF(commodity, ''),
    NULLIF(granted_at, '')::date,
    NULLIF(expires_at, '')::date,
    now(),
    %(run_id)s,
    ST_Multi(ST_GeomFromText(geom_wkt, 4326)),
    source_url
FROM concessions_staging
WHERE ST_IsValid(ST_GeomFromText(geom_wkt, 4326))
ON CONFLICT (cadastre_uid) DO UPDATE SET
    license_status  = EXCLUDED.license_status,
    last_seen_at    = now(),
    pipeline_run_id = EXCLUDED.pipeline_run_id;
"""

COPY_COLS = [
    "cadastre_uid", "holder_name", "license_no", "license_type", "license_status",
    "commodity", "granted_at", "expires_at", "geom_wkt", "source_url",
]

_HTTP_HEADERS = {
    "User-Agent": "galamsey-tracker/1.0 (+https://github.com/Phinart98/galamsey-tracker)"
}


def make_uid(license_no: str, holder: str, license_type: str = "") -> str:
    # Include license_type so rows with the same holder but no license_no stay distinct.
    return hashlib.md5(f"{license_no}:{holder}:{license_type}".encode()).hexdigest()


def parse_date(raw: str) -> str:
    """Return ISO date string or '' on failure."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def fetch_json_page(client: httpx.Client, page: int, page_size: int = 200) -> list[dict]:
    """Return rows from the JSON API for the given page, or [] if unavailable."""
    try:
        r = client.get(API_ENDPOINT, params={"page": page, "size": page_size}, timeout=30)
        if r.status_code == 404:
            return []
        if "application/json" not in r.headers.get("content-type", ""):
            return []
        data = r.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("data", "items", "results", "licenses"):
                if key in data and isinstance(data[key], list):
                    return data[key]
        return []
    except Exception as exc:
        log.warning("JSON API fetch failed", error=str(exc))
        return []


def parse_html_cards(html: str) -> list[dict]:
    """Parse license cards from server-rendered HTML as a fallback.

    Update CSS selectors below after inspecting the live DOM at SOURCE_URL —
    the selectors here are common patterns for cadastre SPAs.
    """
    tree = HTMLParser(html)
    records: list[dict] = []
    for card in tree.css(".license-card, .card, [data-license-id], tr[data-id]"):
        def get(sel: str) -> str:
            node = card.css_first(sel)
            return node.text(strip=True) if node else ""

        holder = get(".holder, .company-name, [data-field='holder']")
        license_no = get(".license-no, .ref, [data-field='license_no']")
        if not holder and not license_no:
            continue
        records.append({
            "holder_name": holder,
            "license_no": license_no,
            "license_type": get(".license-type, [data-field='type']"),
            "license_status": get(".status, [data-field='status']"),
            "commodity": get(".commodity, [data-field='commodity']"),
            "granted_at": get(".granted, [data-field='granted_at']"),
            "expires_at": get(".expires, [data-field='expires_at']"),
            "geom_wkt": "",
            "source_url": SOURCE_URL,
        })
    return records


def iter_cadastre(
    client: httpx.Client,
    max_pages: int | None,
) -> Iterator[dict]:
    """Yield raw concession dicts from JSON API, falling back to HTML on page 1 failure."""
    use_json = True
    page = 1

    while True:
        if max_pages is not None and page > max_pages:
            log.info("Max pages reached", max_pages=max_pages)
            break

        if use_json:
            rows = fetch_json_page(client, page)
            if not rows:
                if page == 1:
                    log.warning("JSON API unavailable on page 1 -- switching to HTML scraping")
                    use_json = False
                    continue
                log.info("JSON API exhausted", last_page=page - 1)
                break
            yield from rows
            page += 1
            continue

        # HTML fallback
        r = client.get(SOURCE_URL, params={"page": page}, timeout=30)
        r.raise_for_status()
        rows_html = parse_html_cards(r.text)
        if not rows_html:
            log.info("HTML scraping exhausted", last_page=page - 1)
            break
        yield from rows_html
        page += 1


def geom_to_wkt(raw: object) -> str:
    """Convert raw geometry (WKT string, GeoJSON dict, or GeoJSON string) to WKT."""
    if not raw:
        return ""
    if isinstance(raw, dict):
        try:
            from shapely.geometry import shape
            from shapely import to_wkt
            return to_wkt(shape(raw), rounding_precision=-1)
        except Exception:
            pass
        # Last resort: pass raw GeoJSON to PostGIS via ST_GeomFromGeoJSON instead of ST_GeomFromText.
        # Caller must detect this and adjust the SQL; for now return empty to skip.
        return ""
    s = str(raw).strip()
    # GeoJSON string
    if s.startswith("{"):
        try:
            return geom_to_wkt(json.loads(s))
        except Exception:
            return ""
    return s


def normalise(raw: dict) -> dict | None:
    """Coerce a raw record into the staging schema; return None to skip."""
    holder = str(
        raw.get("holder_name") or raw.get("holder") or raw.get("company") or ""
    ).strip()
    if not holder:
        return None

    license_no = str(raw.get("license_no") or raw.get("licenseNo") or raw.get("ref") or "").strip()
    geom_wkt = geom_to_wkt(raw.get("geom") or raw.get("geometry") or raw.get("wkt") or "")
    if not geom_wkt:
        log.debug("Skipping row without geometry", holder=holder, license_no=license_no)
        return None

    license_type = str(raw.get("license_type") or raw.get("type") or "").strip()
    return {
        "cadastre_uid": make_uid(license_no, holder, license_type),
        "holder_name": holder,
        "license_no": license_no,
        "license_type": license_type,
        "license_status": str(raw.get("license_status") or raw.get("status") or "").strip(),
        "commodity": str(raw.get("commodity") or "").strip(),
        "granted_at": parse_date(str(raw.get("granted_at") or raw.get("grantedAt") or "")),
        "expires_at": parse_date(str(raw.get("expires_at") or raw.get("expiresAt") or "")),
        "geom_wkt": geom_wkt,
        "source_url": str(raw.get("source_url") or SOURCE_URL),
    }


@click.command()
@click.option("--max-pages", default=None, type=int, help="Stop after N pages")
@click.option("--dry-run", is_flag=True, help="Fetch and normalise but skip database writes")
@click.option(
    "--since",
    default=None,
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Skip licences granted before this date (YYYY-MM-DD)",
)
def main(max_pages: int | None, dry_run: bool, since: datetime | None) -> None:
    """Scrape Minerals Commission cadastre and upsert into concessions table."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ]
    )

    database_url = os.environ.get("DATABASE_URL")
    if not database_url and not dry_run:
        raise click.ClickException("DATABASE_URL environment variable is required")

    since_date: date | None = since.date() if since else None

    # Open the run record BEFORE scraping so it's visible in the audit table
    # even if the HTTP phase crashes. Committed in its own transaction.
    run_id: int | None = None
    if not dry_run and database_url:
        with psycopg.connect(database_url) as boot_conn:
            with boot_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO pipeline_runs (pipeline_name, started_at, status) "
                    "VALUES ('concessions', now(), 'running') RETURNING id"
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
        with httpx.Client(headers=_HTTP_HEADERS) as client:
            rows_buf = io.StringIO()
            writer = csv.writer(rows_buf)
            total = 0
            skipped = 0

            for raw in iter_cadastre(client, max_pages):
                normed = normalise(raw)
                if normed is None:
                    skipped += 1
                    continue
                if since_date and normed["granted_at"]:
                    try:
                        if date.fromisoformat(normed["granted_at"]) < since_date:
                            skipped += 1
                            continue
                    except ValueError:
                        pass
                writer.writerow([normed[c] for c in COPY_COLS])
                total += 1

    except Exception as exc:
        log.error("HTTP scrape failed", error=str(exc))
        mark_run("failed", notes=str(exc)[:1000])
        sys.exit(1)

    log.info("Scrape done", rows=total, skipped=skipped)

    if dry_run:
        rows_buf.seek(0)
        sample = [next(iter(rows_buf)) for _ in range(min(3, total))]
        for line in sample:
            print(line, end="")
        return

    if total == 0:
        log.warning("No valid rows scraped -- nothing written")
        mark_run("success", rows=0)
        return

    with psycopg.connect(database_url) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(STAGING_DDL)

                rows_buf.seek(0)
                copy_sql = f"COPY concessions_staging ({','.join(COPY_COLS)}) FROM STDIN WITH (FORMAT CSV)"
                with cur.copy(copy_sql) as copy_obj:
                    copy_obj.write(rows_buf.read())

                cur.execute(UPSERT_SQL, {"run_id": run_id})
                inserted = cur.rowcount

                cur.execute("TRUNCATE concessions_staging")
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
