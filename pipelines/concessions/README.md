# Concessions Scraper

Scrapes the Minerals Commission cadastre at `https://ghana.revenuedev.org/license`
and upserts results into the `concessions` table.

Runs weekly via GitHub Actions (Sunday 03:00 UTC). Each run writes one row to
`pipeline_runs` for observability.

## What it scrapes

Ghana mining license data: holder name, license number/type/status, commodity,
grant/expiry dates, and the concession polygon geometry.

## Setup

```bash
cd pipelines/concessions
uv sync --extra dev
```

## Usage

```bash
# Dry run (fetch + normalise, no database writes)
DATABASE_URL=postgres://... uv run python -m pipelines.concessions.scrape --dry-run

# Limit pages for testing
DATABASE_URL=postgres://... uv run python -m pipelines.concessions.scrape --max-pages 5

# Full run
DATABASE_URL=postgres://... uv run python -m pipelines.concessions.scrape

# Only licences granted from a date
DATABASE_URL=postgres://... uv run python -m pipelines.concessions.scrape --since 2024-01-01
```

## Endpoint discovery

On first run against a new version of the cadastre site, open DevTools > Network
on `https://ghana.revenuedev.org/license` and look for XHR/fetch calls. The
scraper tries `/api/licenses?page=N&size=200` first; update `API_ENDPOINT` in
`scrape.py` if the real endpoint differs. If no JSON API exists the scraper falls
back to HTML card parsing (update CSS selectors in `parse_html_cards()`).

## License

Data is sourced from the Minerals Commission of Ghana (public record). See the
project-level LICENSE for code licensing.
