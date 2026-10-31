# Galamsey Tracker

Weekly satellite evidence of land cleared in Ghana's southern gold belt, with the licence on the land.

**Live site: [galamseytracker.org](https://galamseytracker.org)**

Every week the tracker finds patches of land that lost their plant cover in the last 12 months, names each one after the nearest town or village, and shows what the Minerals Commission's public register says about the land. For every patch it shows a satellite picture from before the clearing and a recent one, so anyone can see the change for themselves. Patches on land with no licence to mine that have open water in them or within 60 metres carry a "Likely galamsey" label, because mining pits fill with water and farms rarely leave ponds. It is an educated guess, not a finding.

Nobody has to visit a site or file a report for a patch to appear. The whole thing runs on free, open data and rebuilds itself every Monday.

## How it works

1. **Cleared land.** NASA's [OPERA DIST-ALERT](https://lpdaac.usgs.gov/products/opera_l3_dist-alert-hls_v1v001/) product compares each new Landsat and Sentinel-2 picture of a spot with what it normally looks like, and marks land that has lost at least half its plant cover. Marked spots that touch and add up to at least 1 hectare become a patch. Only patches in the forest zone count. North of it and on the coastal plain, most of the clearing we checked was farms, burnt bush and building sites.
2. **Licence on the land.** Each patch is checked against the active licences in the Minerals Commission's [public register](https://ghana.revenuedev.org/), every week. Prospecting licences allow exploring, not mining, so they count as no licence to mine. Licence holders are never named, because a licence on the land does not show who cleared it.
3. **Names.** The nearest OpenStreetMap town or village, and the district from geoBoundaries.
4. **Pictures.** The clearest Copernicus Sentinel-2 picture from before the patch was first seen and a recent one, from Element 84's Earth Search. A patch that keeps growing gets a new recent picture.
5. **Likely galamsey.** For patches with no licence to mine, a water index (green light against shortwave infrared, Xu 2006) from a clear Sentinel-2 picture shows whether there is open water in the patch or within 60 metres of it.
6. **Trend.** The land cleared in the 12 months before the same day each month.
7. **Site.** A static [Astro](https://astro.build/) site with a [MapLibre](https://maplibre.org/) map, built from the results and published on Cloudflare Pages.

The full method, its limits, and what was tried and dropped are on the site's [How it works](https://galamseytracker.org/method) page and in [`docs/validation/2026-10-data-spike.md`](docs/validation/2026-10-data-spike.md). Every source and every public claim is tracked in [`docs/sources.json`](docs/sources.json).

## What it cannot tell you

- Who cleared the land or why. Farms, roads and building sites clear land too.
- Clearing smaller than 1 hectare, or hidden by cloud in every picture for a year.
- Mining on rivers, such as dredging from boats, because it removes no plants.
- Anything outside the eight areas of the southern gold belt covered so far. The savanna north, including the Upper East, is not covered.

## Repository layout

| Folder | What is in it |
|---|---|
| `pipeline/` | The weekly Python job (uv project, package `tracker`), with tests. See [`pipeline/README.md`](pipeline/README.md). |
| `apps/site/` | The Astro site. |
| `data/` | Small results the site is built from: summaries, trend, towns, status. Committed by the weekly run. |
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
uv run python -m tracker.run weekly           # patches, licences, names, summary
uv run python -m tracker.run chips --limit 20 # before and after pictures, newest places first
uv run python -m tracker.run signs --limit 20 # open-water readings
uv run python -m tracker.run trend            # monthly trend points (slow the first time)

cd ../apps/site
npm ci
npm run dev                                   # reads ../../pipeline/out
```

## The weekly run

[`.github/workflows/weekly.yml`](.github/workflows/weekly.yml) runs every Monday at 06:00 UTC, and can be started by hand. It:

1. restores the previous run's working files (place list, readings, pictures) from the `pipeline-state` release,
2. runs the four pipeline commands above,
3. saves the working files back to the release and commits `data/`,
4. publishes the pictures to their own Cloudflare Pages project, `galamsey-tracker-pictures`, so neither project passes Pages' limit of 20,000 files,
5. builds the site and publishes it to the `galamsey-tracker` Pages project, which serves galamseytracker.org.

A failed run still records itself in `data/status.json`, and the site says when an update is late.

Repository secrets: `EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD`, `CLOUDFLARE_API_TOKEN` (Cloudflare Pages edit) and `CLOUDFLARE_ACCOUNT_ID`.

## Licences

- **Code:** AGPL-3.0, see [LICENSE](LICENSE).
- **Data:** each source sets its own terms, listed on the site's [Data](https://galamseytracker.org/data) page.
  - Pictures contain modified Copernicus Sentinel data.
  - NASA OPERA data is NASA open data with no limits on use.
  - geoBoundaries districts and RESOLVE Ecoregions are CC BY 4.0.
  - HydroSHEDS rivers and drainage areas are free to use with credit.
  - OpenStreetMap names and the OpenFreeMap base map are under the ODbL, with credit.
  - The Minerals Commission register is used only to classify the licence on each patch. Its outlines and holder names are not republished.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Ideas and data can also go to hello@galamseytracker.org. For security issues, see [SECURITY.md](SECURITY.md).
