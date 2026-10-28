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

## 9. Licence context from the Minerals Commission cadastre (2026-10-25)
`spike/licences.py`:
- **Source:** the public GeoJSON behind ghana.revenuedev.org/map, 1,067 active licences. 2 are
  unparseable and the rest are repaired with `make_valid`.
- **Classed by the minerals each licence covers.** Restricted Mining Leases cover granite (116),
  sand, gravel, limestone and salt, which is not a right to dig for gold, so they count as
  "no licence".
- **Each cluster gets** the class covering the largest share of its area (at least 25%). Ties go to
  the more permissive licence.

Results for tile 30NXM (1,534 clusters, 4,046 ha, data up to 2026-10-22):

| Licence class | Clusters | Hectares | Share |
|---|---|---|---|
| No licence | 1,123 | 2,849 | 70% |
| Prospecting only (mining not allowed) | 189 | 482 | 12% |
| Large-scale lease | 211 | 656 | 16% |
| Small-scale licence | 11 | 59 | 1% |

Top 5 checks:
- #1 and #2 are large-scale leases (AngloGold Ashanti; Abosso Goldfields).
- #3 and #5 are prospecting-only.
- #4 is a small-scale licence (54% of its area; 34% is in a large-scale lease).

The earlier eye-check called #4 "galamsey". That was wrong in law even though it was right by
appearance. Hence the two-axis model: does it look like mining, and is mining licensed here.

## 10. Place names (2026-10-25)
`spike/places.py`:
- **Districts:** geoBoundaries GHA ADM2 (260 districts, 2019, Ghana Statistical Service, CC BY 4.0).
- **Settlements:** OSM place=city|town|village. Prefer a town within 15 km, otherwise a village
  within 8 km.
- **Result:** all 1,534 clusters are named. Examples: #1 "near Obuasi, Obuasi Municipal", #2 "near
  Damang, Prestea/Huni Valley", #3-#5 "near Dadieso, Wassa Amenfi East".

## 11. Year-on-year: DIST-ANN is NOT usable for a trend; same-date DIST-ALERT is
`spike/annual.py`. DIST-ANN-HLS tile 30NXM, confirmed loss of at least 50%, patches of at least 1 ha:

| Year | Hectares |
|---|---|
| 2023 | 5,890 |
| 2024 | 5,682 |
| 2025 | 2,615 |

The 2025 drop is an artefact, and so is the size of 2023:
- **2023 starts with a backlog.** January 2023 holds about 4x any other month, because the product
  starts on 2023-01-01.
- **The 2025 file is premature.** It was produced on 2026-01-09: December 2025 has 32 sampled pixels
  against 1,652 for December 2024, because late alerts were not yet confirmed.
- **The status codes changed.** Codes 9 and 10 appear only from 2024 onward.

`spike/rolling.py`: the trailing 12 months from the DIST-ALERT granule nearest 22 October each year,
the same rule as the weekly clusters, so the confirmation lag is identical every year.

| 12 months to | Hectares | No licence |
|---|---|---|
| 2024-10-22 | 3,834 | 2,646 (69%) |
| 2025-10-22 | 4,509 | 3,548 (79%) |
| 2026-10-22 | 4,007 | 2,885 (72%) |

**Reading:** no clear trend in this tile over three years. About 4,000 ha are newly cleared each
year, roughly three-quarters of it outside any licence to mine.
- For the site: a same-date rolling series, computed monthly. A backfill from 2024-01 is possible
  from the DIST-ALERT archive.
- Never use DIST-ANN totals in a chart without checking that year's lag and status codes.
- This is one tile, and cloud-driven observation counts also vary by year. State both on /method.

## 12. "Mining signs" score: new water fails; plain DIST clusters are already precise in the belt
`spike/mining_signs.py`, new water from DSWx-S1:
- Water in at least 2 of the looks between 2026-08-23 and 2026-10-22, and never water in at least
  2 looks over the same window in 2025.
- Only 163 ha of new water in the whole tile. Hotspots #3, #4 and #5 got 0 ha despite visible pit
  ponds, and the largest hit was AngloGold's tailings dam (7.7 ha).
- **Reading:** galamsey ponds are mostly smaller than 30 m pixels, or sit in masked terrain. Dropped
  as a signal.

DIST layer features per cluster (`data/dist_features_30NXM.csv`). The 5 known mining sites have high
loss (VEG-ANOM-MAX 75-84 vs a median of 70) and long duration (78-196 days, ongoing). They are kept
as descriptors, not as a score.

**Development check by eye (Claude, not Philip):** random before/after pairs from tile 30NXM.
- **12 random clusters of at least 3 ha** (seed 7):
  - 10 had a clear pair, and **all 10 show mining**: pit fields, ponds, orange exposed ground, and
    2 engineered industrial pits (54, 172).
  - Sheet: `data/sample12_sheet.png`.
- **9 random clusters of 1-3 ha** (seed 11):
  - **8 show mining.** 1 (cluster 1069) is cloud-covered in the after image and cannot be judged.
    None is clearly farm clearing.
  - Sheet: `data/sample_small_sheet.png`.
- **Together with the top 5: 23 of 24 judgeable-or-not patches show mining.**

Context: of 1,534 clusters, 333 are at least 3 ha, and they hold 50% of the area.

**Reading:** inside the core mining belt, DIST confirmed-loss clusters of at least 1 ha are
overwhelmingly mining, so a hand-weighted score adds fragility without adding accuracy. Instead:
- report all clusters as "land cleared", with the measured share from a random check;
- keep the licence class as the second axis;
- run the same random check (about 20 pairs) per tile before that tile is switched on, because
  farm clearing is likely more common at the belt's edges.

The pre-launch check for the public figure stays a human (Philip) task: a single session of about
100 pairs.

## 13. The monthly trend needs three readings per point (2026-10-25)

The first backfill read one DIST-ALERT granule per month (the one nearest the 22nd) and counted
confirmed loss first seen in the 365 days before it. The series dipped to about 2,450 ha from
December 2025 to March 2026, then jumped by 1,560 ha in April. A rolling 12-month total should not
move like that.

**Cause: two lags in DIST-ALERT, at opposite ends of the window.** Tile 30NXM, confirmed heavy-loss
pixels (every 7th sampled) by the month they were first seen:

| First seen | Read Nov 2025 | Dec 2025 | Jan 2026 | Mar 2026 | Apr 2026 | Jul 2026 |
|---|---|---|---|---|---|---|
| Nov 2024 | 2,192 | | | 16 | | |
| Mar 2025 | 2,835 | 2,910 | 2,789 | 2,005 | | 10 |
| Nov 2025 | 43 | 594 | 1,162 | 1,867 | 1,883 | 1,986 |
| Mar 2026 | | | | 108 | 2,666 | 3,261 |

- **Late confirmation:** a pixel is dated to its first detection but only reaches "confirmed" weeks
  or months later, especially in the rainy season. The newest months of any reading are undercounted.
- **Expiry:** about a year after first detection, a pixel drops out of the product. So a reading
  taken long after the window loses its oldest months.

**Fix (method 2026.10.2):** each point unions three readings, on the 22nd of the window's month and of
the months 2 and 4 later, keeping only pixels first seen inside the window. The first reading
supplies the old months before they expire, and the later ones the late confirmations, which
settle to within about 5% by month 4. A point under 4 months old is marked `"settled": false`, and
the weekly run recomputes it until it settles.

**Consequence for the site:** year-on-year claims compare settled points only. Provisional points
are drawn differently and labelled "still being confirmed".

**Result of the backfill (tile 30NXM, 34 points, 20 minutes):** totals are 10 to 65% higher than the
single-reading series, because late confirmations are now counted. The series still swings with
the seasons: clear dry-season skies in December and January let NASA confirm a burst of clearing,
and that burst leaves the window exactly a year later (for example 6,780 ha to 22 December 2024,
then 3,885 ha to 22 December 2025). So the site only compares a month with the same month a year
before. Latest settled pair: 4,740 ha to 22 June 2026 against 4,864 ha to 22 June 2025, about the
same. The share with no licence to mine rose from about 79% in 2024 to 83 to 86% since.

## 14. Haze that the Sentinel-2 cloud mask misses (2026-10-25)

Two of the first 37 image pairs had an after-picture the scene classification (SCL) called clear,
but which was fog (Assin Nsuta, 22 October 2026) or broken cloud (Kwabenakwa). A pair like that is
worse than no pair.

**Test:** the share of pixels that are bright and grey in the true-colour image (every channel at
least 90 and the channels within 35 of each other). Over all 74 pictures: median 0.002. Clear
pictures go up to 0.14 (grey mine tailings at Tarkwa) and 0.12 (a small cloud in a corner at
Damang, still usable). The fogged ones score 0.34 and 0.91.

**Rule:** a picture with more than 25% bright grey pixels is skipped, and the next clearest is
tried. The two places were re-imaged.

**Update the same day:** the five-tile check (section 15) found a third bad picture, broken cloud
with shadows over Eastern Region, scoring 0.22, just under the cut-off. Re-measured over all 120
accepted pictures: the highest clear one is 0.13 (Tarkwa tailings). The cut-off is now **0.18**. A
broader "grey" (darker pixels, wider spread) was tried and rejected: clear pictures of bare ground
scored up to 0.49 on it.

## 15. By-eye check of five more tiles (2026-10-25)

`uv run python -m tracker.check_tile <tile>`: 20 random patches per tile (10 of at least 3 ha, 10 of
1 to 3 ha, seed 7), with before/after pairs, judged by Claude from contact sheets
(`pipeline/out/checks/<tile>/`).

| Tile | Main districts (from the data) | Showed mining | Not mining |
|---|---|---|---|
| 30NWM | Aowin, Wassa Amenfi Central, West and East | 18 of 18 | none (2 no pair) |
| 30NXN | Ahafo Ano South East, Atwima Mponua, Bekwai, Amansie West | 18 of 20 | a building site; a farm field at 7.2 N |
| 30NYM | Atiwa West, Abuakwa South, Kwaebibirem, Denkyembour | 16 of 19 | 2 construction sites by the Accra-Kumasi highway; 1 unclear |
| 30NYN | Atiwa West and East, Kwahu Afram Plains South, Asante Akim North | 13 of 17 | 4 farms or savanna, all north of 6.9 N |
| 30NWN | Atwima Mponua, Asutifi North, Juaboso, Dormaa | 16 of 19 | 2 farm or logging clearings; 1 unclear |

With 30NXM (23 of 24): **104 of 117, 89%.** All five were switched on. The false hits are farms at the
northern edge and construction near towns. A simple "ignore the north" rule would be wrong: a large
pit field sits at 7.24 N in 30NWN. A farm filter could be tested on these 117 labelled patches later.

## 16. Water: clearing upstream of treatment plants (2026-10-25)

`spike/water.py`: HydroBASINS level 12 (Lehner and Grill 2013, free for commercial use), plants from
OpenStreetMap `man_made=water_works`, each snapped to the basin within 2 km that drains the most
area, then every basin upstream of it. Clearing from 15 southern tiles (overlaps removed): 7,940
patches, 22,166 ha.

| Plant | River | Upstream area | Cleared upstream, 12 months to 22 Oct 2026 |
|---|---|---|---|
| Daboase | Pra | 22,853 km2 | **9,025 ha** |
| Weija | Densu | 2,632 km2 | 233 ha |
| Kwanyako | Ayensu | 1,715 km2 | 158 ha |
| Barekese | Offin | 1,538 km2 | 125 ha |
| Owabi | Owabi | 123 km2 | 3 ha |

The upstream areas match published catchments (Pra about 23,000 km2, Densu about 2,600 km2), which
checks the snapping. **Reading:** the Pra carries the story. About 40% of all clearing in the 15
southern tiles drains past Daboase. The Accra link (Weija) is real but small, and much of Accra's
water comes from the Volta at Kpong, which galamsey barely touches. Which towns each plant supplies
must be sourced before anything is published.

## 17. Which satellites, and how often (2026-10-25)

DIST-ALERT granule names for tile 30NXM, 23 October 2025 to 22 October 2026: 102 readings on 97
days. Sentinel-2A 23, Sentinel-2B 25, Sentinel-2C 28, Landsat 8 13, Landsat 9 13. So three quarters
of the readings come from the European satellites. Gap between reading days: median 3, mean 3.8,
longest 32. Readings per month fall from 9 to 12 in the dry season to 3 to 5 from June to September.

## 18. Six-tile trend and the 2025 to 2026 fall (2026-10-25)

`uv run python -m tracker.run trend` over six tiles took 67 minutes from scratch (download bound once
the tile dedupe was indexed: 463 s to 0.2 s, same 6,130 patches). A run with no new reading takes 4 s.
Settled points (hectares cleared in the 12 months before each point, three readings):
June 2024 18,270; December 2024 28,055 (peak); October 2025 27,863; May 2026 18,348. May 2025 to
May 2026 is -25%, but May 2026 is about the same as May 2024 (21,885 vs 21,401 per-tile sums).

`spike/trend_by_tile.py`, May points per tile (ha, tile overlaps counted twice):

| Tile | May 2024 | May 2025 | May 2026 | 2025 to 2026 |
|---|---|---|---|---|
| 30NWM Wassa Amenfi, Aowin | 4,073 | 5,060 | 5,229 | +3% |
| 30NWN Juaboso, Asutifi | 1,474 | 2,454 | 1,773 | -28% |
| 30NXM Dunkwa-on-Offin | 4,528 | 4,855 | 4,661 | -4% |
| 30NXN Amansie West, Atwima | 5,131 | 6,706 | 4,788 | -29% |
| 30NYM Atiwa, Kibi | 1,601 | 2,849 | 2,568 | -10% |
| 30NYN Atiwa, Kwahu | 4,594 | 7,277 | 2,866 | -61% |

No-data shares are flat across years (0 to 4.4%, the 4.4% is a tile edge) and every reading exists,
so the fall is not a data gap. 30NYN gives 60% of the fall, and 3,486 ha of its May 2025 point was
first seen 22 Feb to 22 May 2025: dry season, when fire and farm clearing also remove plants, in the
tile with the most farm false hits (s15). Outside evidence: no independent satellite figure for
2025 or 2026 yet (the Forestry Commission's survey ends December 2024 and still rising); NAIMOS
operations ran through the period; the government says things improved, A Rocha Ghana disputes
official counts. **Decision pending:** do not publish a year-on-year sentence until the 30NYN
early-2025 patches are checked by eye (`spike/spike_2025_check.py`).

## 19. Towns and villages near cleared land (2026-10-25)

`spike/towns_near.py`: OSM named cities, towns and villages inside the six tiles: 3,352. With any
active patch within 1 km of the place's point: 665. With at least 5 ha: 256; 20 ha: 27; 50 ha: 5.
Patches within 1 km of a named place: 1,171 of 6,130 (19%), 3,430 of 16,711 ha. Clearing first seen
in the last 90 days near a place: only 13, because recent clearing is confirmed late, so a "new
near you" line would mislead. OSM is uneven (30NWM has 244 places, 30NYM 1,067), so counts are a
floor. Usable public form: "at least 665 towns and villages have land cleared within 1 km of them".

Also found: the settlements cache was keyed by file name only, so the five newer tiles had no town
names (3,058 of 6,130 places named). Settlements now come from Geofabrik's Ghana extract (Overpass
returned 502 and its mirrors timed out), cached once for all of Ghana: 6,754 named places.

## 20. The early-2025 jump in 30NYN was farm and fire clearing, not mining (2026-10-25)

`spike/spike_2025_check.py T30NYN`: 1,016 patches (3,486 ha) in the May 2025 point were first seen
22 Feb to 22 May 2025. A random 20 (seed 11, half at least 3 ha), each before / soon after / now
(sheets in `pipeline/out/checks/spike-2025-T30NYN/`). **1 of 20 showed mining** (patch 12 at 6.41 N,
yellow pits by a stream, in the south of the tile). The other 19: field blocks in savanna that are
green again a year later, patchy burnt or cleared bush, and one Lake Volta shoreline exposed by a
falling lake level. They sit in the Afram Plains and northern Kwahu, north of the forest.

**Reading:** the May 2025 to May 2026 fall (s18) is mostly one dry season of savanna farm and fire
clearing leaving the 12-month window, so it is not a galamsey trend and must not be published as
one. In the current window the same strip (30NYN north of 6.8 N) is only 443 of 16,711 ha (3%), so
the headline is barely affected, but the trend swings with these dry-season pulses. Also: the
newest small patches across the belt look mostly like farm blocks (mockup review, 2026-10-25),
so the 104 of 117 figure (largest plus a random sample of the latest snapshot) may overstate the
share for small, recent patches. **To do:** mask savanna and lake shore out of the tiles (an
ecological-zone or forest-zone boundary, and the maximum water extent), then redo the trend and a
season-aware random check before any trend sentence or mining share is published.

## 21. Forest-zone mask (2026-10-25)

RESOLVE Ecoregions 2017 (CC BY 4.0) splits southern Ghana into Eastern Guinean forests and the Guinean
forest-savanna mosaic (plus mangroves). On the 23 Oct 2026 snapshot, 5,889 of 6,130 patches (15,964 of
16,711 ha, 96%) lie in the forest ecoregion. The 747 ha outside are the Afram Plains and northern
Ashanti savanna (Kwahu Afram Plains South 176 ha, Asante Akim North 114, Sekyere Afram Plains North 96,
Sekyere Central 88, Mampong 75) and the coastal plain around Kasoa, Weija, Winneba and Gomoa. Of the 40
largest patches it drops 4: the two that look like farm or plantation blocks (60 ha Asante Akim North,
the site's lead picture until now, and 48 ha Sekyere Central) and two coastal ones. Of the 20 early-2025
30NYN patches (s20) it keeps 5, including the one that showed mining, and drops 15 of the 19 that did
not. Pipeline method 2026.10.3 counts only patches whose representative point is in the zone
(`pipeline/forest_zone.geojson`, made by `spike/forest_zone.py`, simplified to about 100 m, 9 KB).

## 22. Small, recent patches inside the forest zone (2026-10-25)

`spike/recent_check.py`: of the 141 active patches under 3 ha first seen since 26 Apr 2026 (inside the
forest zone, 23 Oct snapshot), a random 20 (seed 13), each before (the clearest picture in the 15 months
before first seen) and now. Sheets in `pipeline/out/checks/recent-small/`. Judged by eye at the centre
of each 1.6 km picture, where a 1 to 3 ha patch is a small square.

- **Signs of mining, 8:** yellow and pale pits, ponds or a muddy river channel at the patch (2 and 11
  Abomosu, 5 Bopa, 8 Kwawu, 20 Enchi), and a band of pits and ponds along a valley (7 and 14 Akim Oda,
  the same band, and 16 Manso).
- **A long cleared band, mining or road works, 3:** an orange band of uneven width through forest
  (13 and 15 Ekoso, the same band) and a straight pale band (10 Kuntanase). They could be river-channel
  mining or a new road.
- **Farm blocks, 4:** square field blocks at Agogo (4, 6), Achiase (17) and a Lake Volta peninsula at
  Sempoakurom (9). Agogo and Sempoakurom are at the north-east edge of the forest zone.
- **Cannot tell, 5:** no clear picture since first seen (1, 18, 19), or nothing visible at the centre
  (3, 12).

**Reading:** for small, recent patches the share with signs of mining is 8 of 20 for sure and at most
11 of 20, far below the 104 of 117 for the largest and a random draw of all patches (s12, s15). These
patches are 141 of 5,889 and a small part of the area, so the headline area is barely affected, but
the site must not present "newest" patches as mining, and any published mining share must say which
patches it covers. The forest zone still lets some farm land in at its north-east edge (Asante Akim
North and the Lake Volta shore). Next: an area-weighted, season-aware random check across all tiles
before any share is published.

## 23. Water plants on the live tiles (2026-10-25)

`spike/water_live.py` repeats s16 on the live data (six tiles, forest zone, 23 Oct snapshot: 5,889
patches, 15,964 ha) and on the 15 southern tiles with the forest zone applied (6,886 patches, 18,894 ha).

| Plant | River | Live six tiles | 15 tiles, forest zone |
|---|---|---|---|
| Daboase | Pra | **8,946 ha (56% of live)** | 9,025 ha |
| Weija | Densu | 214 ha | 217 ha |
| Kwanyako | Ayensu | 146 ha | 146 ha |
| Barekese | Offin | 125 ha | 125 ha |
| Owabi | Owabi | 3 ha | 3 ha |

**Reading:** the six live tiles hold almost all the clearing upstream of every plant, so the water
figures can be published from the live data. More than half of all the clearing the site counts drains
past Daboase. The forest zone dropped nothing upstream of Daboase. The Pra basin upstream of Daboase
(HydroBASINS, simplified to 500 m, 6.5 KB) is written to `pipeline/out/water/pra_basin.geojson` for the
home page map. Before publishing, the figure should come from the weekly run, not this spike.

## 24. Trend inside the forest zone (2026-10-25)

Method 2026.10.3 backfill, six tiles, 51 minutes. Rolling 12-month totals to the 22nd: 15,524 ha (Jan 2024),
a peak of 25,693 ha (Dec 2024), 23,686 ha (Oct 2025), 17,341 ha (May 2026, the latest settled point).
May to May: 20,441 to 17,341 ha, 15% lower. The swing is smaller than before the zone (s18) but the
late-2024 peak and the fall after it have not been checked by eye, so the site still prints no direction.
To do before any trend sentence: an eye check of patches that entered and left the window around the peak.

## 25. How old are Google's pictures of our places? (2026-10-26)

Google Earth web, opened with the site's link for the lead place and five of the largest, picture date from
the status bar (screenshots in `.playwright-mcp/earth-*.png`, not committed).

| Place | Google Earth picture | First seen by us |
|---|---|---|
| Kibi (48 ha) | 17 Dec 2024 | 24 Oct 2025 |
| Obuasi (124 ha) | 28 Dec 2022 | 3 Nov 2025 |
| Kunso (46 ha) | 9 Jan 2026 | 14 Nov 2025 |
| Kunso (41 ha) | 13 Dec 2025 | 14 Nov 2025 |
| Babianiha (38 ha) | 28 Dec 2024 | 25 Oct 2025 |
| Sompre (38 ha) | 12 Feb 2026 | 27 Oct 2025 |

**Reading:** for 3 of 6, Google's picture was taken before the clearing began, one almost four years before.
At Kibi it shows standing forest where our 22 Oct 2026 picture shows 48 ha cleared. So the note beside the
Google links ("can be years older, so they may show forest where the land has since been cleared") is right,
and Google pictures must stay a close-up aid, never the evidence.

## 26. What share of the cleared AREA is mining? Area-weighted, season-split random check (2026-10-26)

`spike/share_check.py` (seed 26): 40 active patches from the 23 Oct 2026 snapshot (six tiles, forest zone),
drawn with chance proportional to hectares, so the share that shows mining estimates the share of cleared
area. 20 first seen in the dry season (Nov to Mar: 5,070 patches, 13,527 ha, 85% of the area) and 20 in the
wet season (819 patches, 2,436 ha, 15%). Sheets in `pipeline/out/checks/share/`. Judged by Claude at the
centre of each 1.6 km picture.

| | Signs of mining | Farm fields | Road or long strip | Other or cannot tell |
|---|---|---|---|---|
| Dry season | 17 | 1 (20 Owinso) | 0 | 2 (11 Nkaseim red laterite cut with a camp, 12 Jacobu edge of town) |
| Wet season | 13 | 3 (24 Agogo, 27 Breman Brakwa, 36 Ntotroso) | 3 (22 Akwatia new road, 23 Manso and 37 Asamankese orange bands) | 1 (39 Kasapin, cloud) |

Mining includes three inside the large licensed mine near Ntotroso and Kyekyewere (14, 34, 35).

**Reading:** weighted by area, 0.85 x 17/20 + 0.15 x 13/20 = **about 82% of the cleared area shows signs
of mining**, with a rough 95% range of 68% to 96% (40 patches). It is lower in the wet season, when more
of the new clearing is farm blocks and long orange bands (road works or river-channel mining). This agrees
with the earlier 104 of 117 (s12, s15), which leaned on large patches, and with s22, where small new
patches were less often mining. A publishable form: "about 4 in 5 hectares of the cleared land showed signs
of mining in a random check". Still Claude's judgement only; Philip's one-time check is the second opinion.

## 27. An automatic "mining signs" mark, without machine learning (2026-10-27)

Friends asked which places are probably galamsey. Licence alone is not enough: in the s26 sample, cleared land
with no licence to mine showed mining in 22 of 32 patches (69%), 14 of 17 at 3 ha or more. So we tested plain
measurements from one clear Sentinel-2 scene after each patch was first seen (`spike/signs_features.py`):
bare ground (NDVI < 0.3), a bare-soil index, open water at or within 60 m of the patch (MNDWI > 0), how green
it is now, and shape (elongation, compactness).

**Labelled patches:** 122 judged by eye (s22, s26, and per-patch verdicts read again from the s15 tile sheets
for 30NXN, 30NYM, 30NYN, 30NWN; unclear ones left out). 108 could be measured: 94 mining, 14 not (five
northern farms now outside the forest zone have no outline; a few had no clear scene).

**Stage 1 (`spike/signs_rule.py`, 200 random half splits, thresholds tuned on one half, scored on the other):**
the best combined rule (green now <= 0.2) gave held-out precision of about 90% at the median but 81% at the
10th percentile, barely better than marking everything (87%). It fails the 9-in-10 bar.

**What stood out:** all 14 non-mining patches (farm blocks, a housing layout, earthworks and a building site by
the Accra-Kumasi highway, a laterite cut) had no open water at all. "Any open water at or within 60 m" marked
75 patches, all 75 mining (recall 80%). Because this rule was noticed after looking, it needs a fresh test:
30 new random patches with no licence to mine, judged blind before the water readings are opened
(`spike/signs_holdout.py`, seed 31). Risks to watch: farms beside open rivers, and patches next to someone
else's ponds. Result below.

**Blind batch 1 (2026-10-28):** 30 random active patches with no licence to mine (pool 5,056), judged from the
sheets and written to `verdicts.json` before the readings were opened: 23 mining, 3 not (a quarry or building
site by the coastal highway, two farm blocks), 4 unclear. 29 could be measured. The rule marked 25: 22 mining,
1 not (a neat block in forest, water 0.031), 2 unclear. It marked every measured mining patch (22 of 22) and
left out the quarry, one farm and two unclear patches.
Precision is 22 of 25 (88%) if unclear counts against the rule, 22 of 23 (96%) if unclear is left out. The bar
did not say how to count unclear, so this batch is **not a pass**: it sits just under 9 in 10 on the strict count.
**Batch 2, fixed before it runs:** same rule (any MNDWI > 0 at or within 60 m), unchanged; 30 more random
patches, none from batch 1 or the labels (seed 32); unclear counts against the rule; pass if, pooled over both
batches, at least 9 in 10 marked patches show mining. If it fails, no mark ships.

**Blind batch 2 (2026-10-28, seed 32, judged and saved before unsealing):** 25 mining, 2 not (a straight line cut,
greening farmland), 3 unclear. All 30 measured. The rule marked 27: 24 mining, 3 unclear; it left out both
non-mining patches and missed one mining patch (water 0.0).
**Pooled over both blind batches: 46 of 52 marked patches showed mining (88%), recall 46 of 47.** Under the rule
fixed before batch 2, that is a **fail**: no "mining signs" mark ships. What it does show: of the 6 marked
patches that were not clear mining, only 1 was clearly something else; 5 were unclear from 10 m pictures. The
open-water reading separates clear mining from clear farms and roads well, but not well enough on the pictures
we can judge to put a per-place label on the site.
