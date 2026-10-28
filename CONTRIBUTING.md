# Contributing to Galamsey Tracker

Thank you for wanting to help.

## Before you start

- Read the [Code of Conduct](CODE_OF_CONDUCT.md). It applies to all project spaces.
- For anything bigger than a small fix, open an issue first so we can agree on the approach.
- Read the method and its limits in [`docs/validation/2026-10-data-spike.md`](docs/validation/2026-10-data-spike.md) before changing how anything is counted.

## Setting up

See "Running it yourself" in the [README](README.md).

## How to contribute

1. Fork the repository and create a branch from `master`.
2. Make your change and run the checks below.
3. Write commit messages as a short heading followed by bullet points.
4. Open a pull request against `master`. Say what changed and why.

## Checks

- **Pipeline:** `cd pipeline && uv run ruff check . && uv run pytest`. New behaviour needs a test.
- **Site:** `cd apps/site && npm run build`. The build must also pass with no data, which is how CI runs it.

## Rules that keep the site honest

- Every number or claim shown to the public needs an entry in [`docs/sources.json`](docs/sources.json).
- Describe the licence on the land. Never name licence holders, and never call a single place illegal. "Likely galamsey" is worded as a guess and must stay that way.
- A change to the method needs evidence first: a check against pictures or a published result, recorded in the validation log, before it reaches the site.
- Plain English on the site, for readers who are not scientists.
- No secrets in commits. The weekly job reads them from GitHub repository secrets.
