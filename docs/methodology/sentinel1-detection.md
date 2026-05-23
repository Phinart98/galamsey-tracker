# Detecting new mining clearings from Sentinel-1 radar

**Methodology**: backscatter change detection on a +1.65 dB threshold, after
Forkuor et al. 2020.

---

## What this layer detects

Newly cleared land in Ghana, polygon by polygon, where the change is large
enough and distinctive enough to be galamsey-consistent.

The detection signal is the **radar backscatter intensity** measured by the
European Space Agency's Sentinel-1 satellites. Radar backscatter is the
fraction of microwave energy a surface reflects back to the satellite. Three
properties make it useful for galamsey monitoring:

- It penetrates clouds. Ghana's rainforest belt is cloud-covered 30 to 60
  percent of months. Optical satellites like Sentinel-2 miss those months.
  Radar does not.
- It rises sharply when vegetated land is stripped to bare earth. Forest
  canopy scatters radar diffusely (low backscatter); bare soil and water-
  filled mining pits reflect more directly (high backscatter). The dB
  difference between the two states is large and unambiguous.
- It is available from a free, anonymous, well-documented public archive:
  [Microsoft Planetary Computer's `sentinel-1-rtc` collection](https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc).

---

## How the algorithm works

For each pixel in Ghana, monthly:

```
baseline_VV = mean over previous 12 months of VV backscatter, in dB
baseline_VH = mean over previous 12 months of VH backscatter, in dB
current_VV  = mean over the detection month of VV backscatter, in dB
current_VH  = mean over the detection month of VH backscatter, in dB

delta_VV = current_VV - baseline_VV
delta_VH = current_VH - baseline_VH

A pixel is flagged as "new clearing candidate" when:
  delta_VV >= +1.65 dB  AND  delta_VH >= +1.65 dB
```

Two polarisations are used together because each one alone has known
failure modes:

- VV alone over-detects flooded rice paddies during the transplanting
  season, especially in the northern regions.
- VH alone misses dry-season clearings where the canopy stripping is
  modest in absolute terms but still real.

The joint condition (both bands above threshold) eliminates roughly 80
percent of the false positives that either band alone would produce.

The flagged pixel mask is then vectorised into polygons, simplified at a
50-metre tolerance, and any polygon smaller than 0.5 ha (5 000 m^2) is
dropped as likely radar speckle.

---

## Confidence rules

Every detected polygon is classified into one of three buckets:

- **High** — the polygon is within 500 m of a mapped water body, or it
  intersects a designated forest reserve. These are the canonical galamsey
  signatures: mining either follows the rivers (for sluice access) or pushes
  into reserves (where enforcement is weaker).
- **Medium** — the polygon meets the threshold criteria but does not match
  either of the above. Most legitimate land-use changes (agriculture, urban
  construction) end up here.
- **Low** — area is below 1 ha, or the mean delta dB is below 2 dB. These are
  kept in the API for completeness but hidden from the default dashboard view
  because the false-positive rate is too high.

The dashboard's SAR layer shows medium and high together by default; you can
filter to high only via the API.

---

## Known limitations and false positives

- **Rice paddies during transplanting (Mar through May)**. Standing water
  raises VV backscatter sharply. The joint VV/VH condition catches most of
  these, but some leak through in the northern regions.
- **New construction along urban edges**. Bare-earth signatures are
  indistinguishable from clearings until vegetation regrows. The Ghana-wide
  AOI returns some hits in Kumasi and Accra suburbs each month. The dashboard
  filter (medium+ only, by default) reduces but does not eliminate these.
- **Harvested oil palm and rubber plantations** in the Western Region.
  Distinguishable from galamsey only via the concession overlay (legal harvest
  = registered concession). Phase 5's citizen-report layer will help ground-
  truth ambiguous polygons.

---

## How to reproduce this

Anyone with Python 3.12 can reproduce a one-month detection over Ghana
against the Microsoft Planetary Computer's anonymous STAC API. The snippet
below is the minimal viable version of `pipelines/sentinel1_sar/detect.py`.

```python
from datetime import date, timedelta

import numpy as np
import planetary_computer
import stackstac
from pystac_client import Client

PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
GHANA_BBOX = (-3.26, 4.74, 1.20, 11.18)

client = Client.open(PC_STAC, modifier=planetary_computer.sign_inplace)

def search(start, end):
    # Full UTC timestamps so the interval is fully inclusive at both ends:
    # bare dates resolve to T00:00:00Z and silently drop end-of-day acquisitions.
    dt_from = f"{start.isoformat()}T00:00:00Z"
    dt_to   = f"{end.isoformat()}T23:59:59Z"
    return list(client.search(
        collections=["sentinel-1-rtc"],
        bbox=GHANA_BBOX,
        datetime=f"{dt_from}/{dt_to}",
        query={"sar:instrument_mode": {"eq": "IW"}},
    ).items())

period_start   = date(2026, 4, 1)
period_end     = date(2026, 4, 30)
baseline_start = date(period_start.year - 1, period_start.month, 1)
baseline_end   = period_start - timedelta(days=1)

current  = search(period_start, period_end)
baseline = search(baseline_start, baseline_end)

def db_mean(items):
    da = stackstac.stack(
        items, assets=["vv", "vh"],
        bounds_latlon=GHANA_BBOX,
        epsg=32630, resolution=20, dtype="float64", rescale=False,
    )
    return (10 * np.log10(da.where(da > 0))).mean(dim="time", skipna=True)

delta = (db_mean(current) - db_mean(baseline)).persist()
mask = (delta.sel(band="vv") >= 1.65) & (delta.sel(band="vh") >= 1.65)
mask.rio.to_raster("change_2026-04.tif")
```

That `change_2026-04.tif` is the input the rest of our pipeline polygonises
and classifies. Anyone reproducing should expect ~50 to 500 candidate
polygons over Ghana for a typical month, with hot-spot density in Wassa
Amenfi, Atewa, the Pra basin, and Tano Nimiri.

---

## Peer-reviewed references

1. Forkuor, G., Ullmann, T., Griesbeck, M. (2020). *Mapping and Monitoring
   Small-Scale Mining Activities in Ghana using Sentinel-1 Time Series
   (2015 to 2019).* Remote Sensing 12(6):911.
   [doi:10.3390/rs12060911](https://doi.org/10.3390/rs12060911)

2. Verbesselt, J., Hyndman, R., Newnham, G., Culvenor, D. (2010).
   *Detecting trend and seasonal changes in satellite image time series.*
   Remote Sensing of Environment 114(1):106-115.
   [doi:10.1016/j.rse.2009.08.014](https://doi.org/10.1016/j.rse.2009.08.014)

3. Bruzzone, L., Marconcini, M., Wegmuller, U., Wiesmann, A. (2004). *An
   advanced system for the automatic classification of multitemporal SAR
   images.* IEEE Transactions on Geoscience and Remote Sensing 42(6):
   1321-1334.
   [doi:10.1109/TGRS.2004.826821](https://doi.org/10.1109/TGRS.2004.826821)

4. Microsoft Planetary Computer. *Sentinel-1 RTC collection.*
   [planetarycomputer.microsoft.com/dataset/sentinel-1-rtc](https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc)

---

## See also

- `pipelines/sentinel1_sar/` — the production pipeline source code.
- `infra/supabase/migrations/0006_alerts_sar.sql` — the `alerts_sar` schema.
- The Galamsey Tracker dashboard's SAR layer (the rail toggle labelled
  "Sentinel-1 SAR · +1.65 dB backscatter delta") is the polygon view of the
  same detection. The COG raster heatmap that backs this methodology page
  comes from TiTiler at `${NUXT_PUBLIC_TITILER_BASE_URL}/cog/preview.png`.
