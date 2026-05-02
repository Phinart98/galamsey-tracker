# Methodology

This directory contains the methodology documentation for every data layer
in the Galamsey Tracker. Each document explains what the layer detects, how
the algorithm works, known limitations, and how to reproduce the results.

The goal: a Mongabay journalist or KNUST researcher should be able to read
these docs and independently verify our findings.

## Documents

| File | Layer | Status |
|---|---|---|
| `gfw-alerts.md` | GFW Integrated Deforestation Alerts | Phase 2 |
| `sentinel1-detection.md` | Sentinel-1 SAR change detection | Phase 3 |
| `water-quality.md` | Sentinel-2 NDTI river turbidity | Phase 4 |
| `reports.md` | Citizen reports (web / Telegram / SMS) | Phase 5 |
| `incidents.md` | News incident extraction (Claude API) | Phase 7 |
| `verification.md` | Cross-reference confidence scoring | Phase 7 |

## Model references

- [MapBiomas ATBD Collection 10](https://brasil.mapbiomas.org/wp-content/uploads/sites/4/2025/08/ATBD-Collection-10-v2.pdf)
- [Climate TRACE methodology repo](https://github.com/climatetracecoalition/methodology-documents)
- [Forkuor et al. 2020 — Sentinel-1 mining detection in Ghana](https://www.mdpi.com/2072-4292/12/6/911)
