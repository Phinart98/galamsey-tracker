# Galamsey Tracker

Weekly satellite evidence of land cleared in Ghana's southern gold belt, with the licence on the land.

Every week the tracker finds patches of land that lost their plant cover in the last 12 months, names each one after the nearest town or village, and shows what the Minerals Commission's public register says about the land. For larger patches it shows a satellite picture from before the clearing and a recent one, so anyone can see the change for themselves. Patches on land with no licence to mine that have open water in or beside them carry a "Likely galamsey" label, because mining pits fill with water and farms rarely have ponds. It is an educated guess, not a finding.

Nobody has to visit a site or file a report for it to appear. The whole thing runs on free, open data and rebuilds itself every Monday.

> **Status:** private preview. The public site launches soon.

## How it works

1. **Cleared land.** NASA's [OPERA DIST-ALERT](https://lpdaac.usgs.gov/products/opera_l3_dist-alert-hls_v1v001/) product compares each new Landsat and Sentinel-2 picture of a spot with what it normally looks like, and marks land whose plant cover has dropped by half or more. Marked spots that touch and add up to at least 1 hectare become a patch. Only patches in the forest zone count, where the gold is. Outside it, most of the clearing we checked was farms, burnt bush and building sites.
2. **Licence on the land.** Each patch is checked against the active licences in the Minerals Commission's [public register](https://ghana.revenuedev.org/). Prospecting licences allow exploring, not mining, so they count as no licence to mine. Licence holders are never named.
3. **Names.** The nearest OpenStreetMap town or village, and the district from geoBoundaries.
4. **Pictures.** The clearest Copernicus Sentinel-2 picture from before the patch was first seen and a recent one, from Element 84's Earth Search.
5. **Likely galamsey.** For patches with no licence to mine, a water index (green light against shortwave infrared, Xu 2006) from a clear Sentinel-2 picture shows whether there is open water in the patch or within 60 metres of it.
6. **Trend.** The land cleared in the 12 months before the same day each month.
7. **Site.** A static [Astro](https://astro.build/) site with a MapLibre map, built from the results and published to Cloudflare Pages.

The full method, what it cannot tell you, and what was tried and dropped are on the site's "How we know" page and in [`docs/validation/2026-10-data-spike.md`](docs/validation/2026-10-data-spike.md). Every source and every public claim is tracked in [`docs/sources.json`](docs/sources.json).

## What it cannot tell you

- Who cleared the land or why. Farms, roads and building sites clear land too.
- Clearing smaller than 1 hectare, or hidden by cloud in every picture for a year.
- Mining on rivers, such as dredging from boats, because it removes no plants.
- Anything outside the six areas of the southern gold belt covered so far.

## Repository layout

| Folder | What is in it |
|---|---|
| `pipeline/` | The weekly Python job (uv project, package `tracker`), with tests. See [`pipeline/README.md`](pipeline/README.md). |
| `apps/site/` | The Astro site. |
| `data/` | Small results the site is built from: summaries, trend, towns, status. Committed by the weekly job. |
| `docs/` | The source register, the validation log and the research report. |
| `spike/` | One-off experiments behind the method, kept for the record. |
| `design/` | Design mockups. |

## Running it yourself

You need Python 3.12 with [uv](https://docs.astral.sh/uv/), Node.js 22, and a free [NASA Earthdata](https://urs.earthdata.nasa.gov/) account in `~/.netrc` (on Windows `~/_netrc`):

```
machine urs.earthdata.nasa.gov login YOUR_USERNAME password YOUR_PASSWORD
```

```bash
cd pipeline
uv sync --extra dev
uv run pytest
uv run python -m tracker.run weekly        # patches, licences, names, summary
uv run python -m tracker.run chips         # before and after pictures
uv run python -m tracker.run signs         # open-water readings
uv run python -m tracker.run trend         # monthly trend points

cd ../apps/site
npm ci
npm run dev                                # reads ../../pipeline/out
```

## The weekly run

`.github/workflows/weekly.yml` runs every Monday at 06:00 UTC, and can be started by hand. It restores the previous run's working files (place list, readings, pictures) from the `pipeline-state` release, runs the four steps above, saves the working files back to the release, commits `data/`, then builds the site and publishes it to Cloudflare Pages. A failed run still records itself in `data/status.json`, and the site says when an update is late.

Repository secrets: `EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD`, `CLOUDFLARE_API_TOKEN` (Cloudflare Pages edit) and `CLOUDFLARE_ACCOUNT_ID`.

## Licences

- **Code:** AGPL-3.0, see [LICENSE](LICENSE).
- **Data:** each source sets its own terms. Sentinel-2 images contain modified Copernicus Sentinel data. NASA OPERA data is open with no restrictions. OpenStreetMap names are under the ODbL. geoBoundaries districts and RESOLVE Ecoregions are CC BY 4.0. The Minerals Commission register is used only to classify the licence on each patch and is not republished.

## Earlier version

The first version (Nuxt, FastAPI, Supabase, citizen reports) is kept at the tag [`v0-nuxt-supabase`](https://github.com/Phinart98/galamsey-tracker/tree/v0-nuxt-supabase). It never got reliable source data, and this version replaced it in October 2026.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Security issues: see [SECURITY.md](SECURITY.md).
