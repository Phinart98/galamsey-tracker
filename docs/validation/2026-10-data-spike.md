# Data spike log (M1), started 2026-10-24

Purpose: prove every data source against a known answer before any pipeline or CI work.
Scripts live in `spike/`. Raw downloads go in `spike/data/` (not committed).

## 1. OPERA products over the southern mining belt (bbox -3.2,5.0 to -0.5,7.5)
Script: `spike/probe_cmr.py`. Granules acquired 2026-09-01 to 2026-10-24, from the NASA CMR search.

| Product | Granules | Cadence seen | Latency (acquisition to CMR update) | Access |
|---|---|---|---|---|
| `OPERA_L2_RTC-S1_V1` (terrain-corrected Sentinel-1, 30 m) | 1003 | passes about every 6 days per track, S1C and S1D both present | median 11 h, max 34 h | Earthdata login (ASF) |
| `OPERA_L3_DIST-ALERT-HLS_V1` (vegetation disturbance, 30 m) | 282 | near daily (HLS) | about 2 days (from file names) | Earthdata login (LP DAAC) |
| `OPERA_L3_DSWX-S1_V1` (surface water from radar, 30 m) | 371 | about every 6 days | median 36 h | Earthdata login (PO.DAAC) |
| `OPERA_L3_DSWX-HLS_V1` (surface water from optical) | 297 | near daily | median 68 h | Earthdata login |
| `OPERA_L3_DIST-ALERT-S1_V1` | **0** | none | none | **not in CMR** |

Findings:
- **DIST-ALERT-S1 does not exist in CMR over Ghana.** The research report's claim was wrong. The only
  ready-made radar comparator we lose is this one. DIST-ALERT-HLS remains.
- **DSWx-S1 is a new candidate signal.** Galamsey pits fill with water. "Surface water where there
  was none a year ago, away from rivers and reservoirs" is a mining signature that radar sees through
  cloud. Add it to the M1 checks.
- Every OPERA file needs a free NASA Earthdata login. Unauthenticated GETs return 401.

## 2. Sentinel-2 clear scenes (Earth Search, `sentinel-2-c1-l2a`)
Script: `spike/probe_s2_clouds.py`. Tiles 30NWM, 30NVM, 30NWN, 30NVL, 2023-01 to 2026-10. Scene-level cloud.

| Month | Scenes per tile per month under 30% cloud | under 10% cloud |
|---|---|---|
| Jan | 4.9 | 1.5 |
| Feb | 3.1 | 1.3 |
| Mar | 2.4 | 0.5 |
| Apr | 2.2 | 0.8 |
| May | 1.4 | 0.1 |
| Jun | 0.2 | 0.1 |
| Jul | 0.4 | 0.1 |
| Aug | 0.1 | 0.0 |
| Sep | 0.4 | 0.1 |
| Oct | 1.2 | 0.4 |
| Nov | 3.0 | 0.4 |
| Dec | 4.2 | 1.2 |

Findings:
- From June to September optical is effectively blind at scene level. Per-pixel Cloud Score+
  composites may recover some views (still to test), but the product cannot depend on optical
  for those months.
- Consequence for the site: in rainy months the bulletin runs on radar. Before/after images always
  show their real capture date ("latest clear view: 14 May").

## 3. Validation datasets
- **Barenblitt et al. 2021** (Mendeley `s4rfcckr39`, CC BY 4.0). Downloaded.
  - `MiningConversion_2007-2017Vec`: 53,793 polygons. The `classifica` field is the conversion year.
    Hectares by year: 2007 333, 2008 455, 2009 413, 2010 1701, 2011 1763, 2012 2081, 2013 2344,
    2014 5783, 2015 5263, 2016 3115, 2017 3443. The years add up to about 26,700 ha.
  - `FullConversiontoMiningExtent2019`: 7,622 polygons, 34,216 ha. `MineType` 1 covers 29,199 ha and
    `MineType` 2 covers 5,017 ha (presumably artisanal and industrial, still to check).
  - Neither file adds up to the paper's headline of about 47,000 ha. That gap needs explaining before
    we cite either number.
- **Forkuor et al. 2020** reports 102, 60 and 33 km² of new mining for 2015/16-2016/17,
  2016/17-2017/18 and 2017/18-2018/19 over its own study area.
  - That is about 2x Barenblitt's figure for roughly the same years, so the two published sources
    disagree on totals.
  - Plan: reproduce Forkuor's method against Forkuor's own numbers, and use Barenblitt for
    **spatial agreement** (does our detector find the same places), not for totals.
- **SmallMinesDS** (Hugging Face `ellaampy/SmallMinesDS`, **CC BY-SA 4.0**, updated 2025-10-09).
  Used only to score our detector, so no published output is derived from it.

## Next (needs an Earthdata login)
1. RTC-S1: build annual-minimum VH stacks for 2015-2019 over Forkuor's study area, apply +1.65 dB,
   and compare with 102/60/33 km² and with Barenblitt polygons.
2. DIST-ALERT-HLS and DSWx-S1: do they flag known 2024-2026 sites?
3. Measure memory and time per 50 km tile on a 16 GB machine.

Note: OPERA RTC-S1 coverage starts in 2016 (per the research report). Reproducing Forkuor's
2015/16 pair may need Planetary Computer `sentinel-1-rtc` or ASF HyP3 RTC instead. Still to check.

## 4. Access confirmed (2026-10-25)
Earthdata login works for ASF (RTC-S1), LP DAAC (DIST-ALERT-HLS) and PO.DAAC (DSWx-S1). ASF needs a
one-time app authorisation in the browser.

RTC-S1 coverage over Amansie and Offin (CMR counts):

| Year | Granules | Note |
|---|---|---|
| 2015 | 0 | no coverage |
| 2016 | 120 | |
| 2017 | 219 | |
| 2018 to 2021 | about 360 per year | S1A and S1B together |
| 2022 to 2024 | 174 to 208 | S1A only |
| 2025 | 294 | S1C added |
| 2026 | 354 | S1D added; a new track T139 appears |

Sample counts differ by about 3x between years. An annual minimum falls as the sample count rises, so
the detector keeps one track at a fixed 12-day spacing (31 acquisitions in each year from 2017 to 2019).

## 5. Forkuor reproduction, first pass (FAILS the gate as-is)
Script: `spike/forkuor.py`.
- **Method:** VH annual minimum in dB after a 3x3 mean, track T147, threshold ±1.65 dB.
- **Area:** -1.80,5.90 to -1.45,6.25 (Amansie and Obuasi, about 1,500 km²).
- **Runtime:** 37 min for 93 acquisitions, about 24 s per date over home broadband. Almost all of
  it is network time.

| Pair | Rise ≥ +1.65 dB | Fall ≤ -1.65 dB |
|---|---|---|
| 2017 to 2018 | 33.4 km² | 27.7 km² |
| 2018 to 2019 | 10.6 km² | 75.8 km² |

**Compared with Barenblitt in the same area** (`compare_barenblitt.py`, `objects.py`). Barenblitt maps
813 ha mined by 2017 and 796 ha newly mined in 2018 to 2019.
- **Pixel level:** precision 6% (rise) and 3% (fall) against all Barenblitt mining. Recall of new
  2018-19 mining is 12% (rise) and 19% (either direction).
- **Clusters, rise, 2017 to 2018:**
  - at least 2 ha: 39% touch known mining;
  - at least 5 ha: 50% touch known mining;
  - found 61 of 313 Barenblitt mine patches.
- **Fall direction:** mostly noise (5 to 22% touch mining). The large 2019 fall is probably a
  wetness effect. My earlier reasoning that ponds lower backscatter does not hold as a standalone
  rule.

**Reading:** a single per-pixel annual-minimum threshold does not work as a primary detector here.
Large rising clusters carry real signal (about half land on known mining), but recall is low and
false alarms are many. Two caveats work in the method's favour:
- Barenblitt is Landsat-based and may under-map small pits.
- Forkuor's study area was river corridors, not whole landscapes.

Even so, the gate is not met. Do not wire this into a pipeline.

Next candidates:
- (a) Context filters: river-corridor restriction, minimum cluster size, two-year persistence,
  DSWx-S1 new-water and DIST-ALERT-HLS agreement.
- (b) A supervised classifier on per-pixel radar features (annual min, mean and std of VV and VH, and
  their year-on-year change), plus dry-season Sentinel-2 indices where available. Labels come from
  Barenblitt and SmallMinesDS, evaluated with spatial cross-validation. This is the approach recent
  work uses (Gallwey 2020, SmallMinesDS 2025, the annah-belle repo).

## 6. Your idea: "see it for yourself" before/after imagery (2026-10-25)
Google Earth has no public API for historical imagery (the Earth API shut down in 2015), and its
terms forbid automated download and republishing. Sentinel-2 at 10 m works instead.
`spike/before_after.py` picks the clearest dry-season scene for each period from Earth Search and crops it.
- **Collection fallback:** `sentinel-2-c1-l2a` has almost no scenes before 2019, so we fall back to
  `sentinel-2-l2a`. This recovers clear 2016-2018 scenes.
- **Offin at Dunkwa, 2017-01-27 vs 2026-01-25** (`data/offin_dunkwa.png`): the river was already brown
  in 2017. The new pits and scars along the river to the NE and E are plainly visible.

## 7. DIST-ALERT-HLS hotspots, eye-checked (tile 30NXM, latest granule 2026-10-22)
`spike/hotspots.py`:
- **Rule:** confirmed loss of at least 50% (VEG-DIST-STATUS 6 or 8) within the last 365 days, as
  8-connected clusters of at least 1 ha. VEG-DIST-DATE counts days since 2020-12-31.
- **Result:** 1,534 clusters covering 4,046 ha. 28% are within 90 m of Barenblitt's 2019 mining.

The top 5, checked by eye with before/after chips (`data/hotspots_sheet.png`):

| # | Lat, lon | Size | What it is |
|---|---|---|---|
| 1 | 6.206, -1.721 | 124 ha | **Industrial**: tailings dams and an engineered pit. Obuasi, AngloGold Ashanti. Not galamsey. |
| 2 | 5.488, -1.851 | 27 ha | Engineered open pit with haul roads. Industrial-style (Bogoso/Prestea area). Ambiguous. |
| 3 | 5.856, -1.919 | 25 ha | Galamsey: patchwork pit ponds expanding |
| 4 | 5.813, -2.013 | 17 ha | Galamsey: new pits pushing into forest |
| 5 | 5.832, -1.911 | 17 ha | Galamsey: pit fields expanding |

Findings:
- DIST-ALERT finds real mining, and an eye-check of a before/after pair is quick and decisive.
- **It cannot tell galamsey from licensed large-scale mines.** We need a large-scale mine mask: the
  Minerals Commission lease boundaries if obtainable, or industrial footprints from Tang & Werner
  2023 / Maus v2. Masked hotspots are labelled "industrial mine expansion", never galamsey.
- Some hotspots will be farm clearing. That is what the monthly eye-check measures.

## 8. River colour (NDTI) on the Pra (fails as a trend measure)
`spike/river_colour.py`:
- **Method:** points every 100 m along the OSM centreline, grouped into 10 km reaches. Each value is
  the dry-season median of NDTI = (red - green)/(red + green), using only SCL water pixels.
- **Scenes:** up to 4 per tile per season.
- **Runtime:** 35 min for 4 seasons on home broadband.

Results:
- **Season medians:** 2016/17 roughly 0.04-0.10 (very few samples), 2019/20 roughly 0.15-0.19,
  2022/23 roughly 0.11-0.12, 2025/26 roughly 0.10-0.16. Every value from 2019 onward reads as turbid.
- **Scene noise exceeds year-to-year change.** Within one season, scene medians range from 0.084 to
  0.215 (2019/20). The uniform 2022 dip sits inside that noise. It is not a processing error: the
  offset is -0.1 with baseline 05.xx for all three seasons checked.
- **Too few water pixels.** SCL rarely classes brown water as water: most cells have fewer than 30
  samples, 2016 has almost none, and reaches 10-22 are missing. The mask keeps the clearer pixels,
  which biases the index.
- The OSM name for the Offin is not "Offin" (try "Ofin"). Birim is split across two name variants.

**Reading:** a year-on-year colour trend per reach is not reliable with this method.

What a v1 can honestly show:
- **Before/after river images.** They are compelling and checkable.
- **A coarse status** per reach (brown vs clear, with the image date and the sample count).

A trend chart needs a fixed water mask (DSWx-HLS or JRC surface-water occurrence, centre of the
channel only), many more scenes per season, and a stable reference water body. That is research,
not v1.
