# Contributing to Galamsey Tracker

Thank you for wanting to help. Every pull request moves this forward.

## Before you start

- Read the [Code of Conduct](CODE_OF_CONDUCT.md) — it applies to all project spaces.
- Check [open issues](https://github.com/Phinart98/galamsey-tracker/issues) before opening a new one.
- For significant changes, open an issue first to discuss the approach.

## Development setup

See the "Running locally" section in [README.md](README.md).

## How to contribute

1. Fork the repository and create a branch from `main`.
2. Make your changes. Run tests before committing.
3. Commit using the format: `heading line` followed by bullet sub-points. No
   `Co-Authored-By` trailers. No em-dashes in commit messages.
4. Open a pull request against `main`. Describe what changed and why.

## Code standards

**Python**: ruff + mypy. Run `pre-commit run --all-files` before pushing.
**TypeScript/Vue**: eslint + prettier. Run `pnpm lint` in `apps/web/`.
**No secrets in commits**: `.env.local` is gitignored; `.env.example` is the
source of truth for what secrets exist.

## Methodology contributions

Every map layer must have a corresponding entry in `docs/methodology/`. If
you add or modify a data layer, update the methodology doc. No layer ships
without methodology.

## Translations

English is the primary language. Twi (Akan) is the first translation target.
Translation files live in `apps/web/locales/`.

## Good first issues

Look for issues tagged `good first issue` on GitHub. Pipeline fixes, UI
accessibility improvements, and translation contributions are great starting
points.
