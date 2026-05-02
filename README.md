# Galamsey Tracker

An open-source, citizen-facing platform that aggregates satellite deforestation
alerts, water-quality data, and community incident reports on illegal artisanal
gold mining ("galamsey") in Ghana.

> **Status**: Phase 0 — bootstrapping. Production URL coming soon.

---

## Why this exists

Galamsey has polluted more than 60% of Ghana's water bodies and degraded
44 of 288 forest reserves. Credible monitoring tools exist — galamStop,
CERSGIS DIGITS, SERVIR-WA — but none are citizen-facing, methodology-
transparent, or open-source. This platform fills that gap.

## What it does

- **Satellite alerts**: GFW integrated alerts (RADD + GLAD) and our own
  Sentinel-1 SAR change detection (Forkuor et al. 2020 method)
- **Water quality**: Sentinel-2 NDTI turbidity index for the Pra, Birim,
  Ankobra, Tano, and Offin river basins
- **Community reports**: web form, Telegram bot, SMS, and USSD (Africa's
  Talking) with photo + GPS
- **Incident timeline**: news scraper across major Ghanaian outlets,
  structured extraction via Claude API
- **Methodology**: every layer has a published, peer-reviewed methodology
  page so journalists and researchers can replicate independently

## Stack

| Layer | Choice |
|---|---|
| Web | Nuxt 3 + MapLibre GL + Tailwind CSS (Vercel) |
| API | FastAPI + GeoAlchemy2 + PostGIS (Cloud Run) |
| Database | Supabase Postgres + PostGIS + Auth |
| Vector tiles (static) | PMTiles on Cloudflare R2 |
| Vector tiles (dynamic) | Martin on Cloud Run |
| Raster tiles | TiTiler on Cloud Run |
| Object storage | Cloudflare R2 |
| SMS / USSD | Africa's Talking |
| Pipelines | Python via GitHub Actions cron |

## Running locally

### Prerequisites

- Node.js 20+, pnpm 9+
- Python 3.12+, uv
- Docker (for local Postgres+PostGIS)
- A Supabase project with PostGIS enabled

### Setup

```bash
# Clone
git clone https://github.com/Phinart98/galamsey-tracker.git
cd galamsey-tracker

# Copy environment variables
cp .env.example .env.local
# Fill in your values in .env.local

# Web
cd apps/web
pnpm install
pnpm dev

# API (separate terminal)
cd apps/api
uv sync
uv run uvicorn main:app --reload
```

## Licenses

- **Code**: AGPL-3.0 — see [LICENSE](LICENSE)
- **Data**: CC-BY-4.0 (derived alerts), ODbL (boundary data from OSM)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All contributors must follow the
[Code of Conduct](CODE_OF_CONDUCT.md).

## Distribution allies

- Erastus Asare Donkor (JoyNews) — investigative galamsey journalist
- Ghana Coalition Against Galamsey (Dr. Ken Ashigbey)
- A Rocha Ghana (BRACE Project)
- WACAM, IMANI Africa, ACEP

## Acknowledgements

Built on the shoulders of GFW, CERSGIS, SERVIR-WA, and the Forkuor et al.
2020 Sentinel-1 methodology. This platform extends, not replaces, their work
by making it citizen-readable and open-source.
