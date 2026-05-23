"""Compute the Forkuor 2020 backscatter-delta change mask.

Algorithm:

  baseline_VV = mean(VV_dB) over [period_start - baseline_months, period_start)
  baseline_VH = mean(VH_dB) over the same window
  current_VV  = mean(VV_dB) over [period_start, period_end]
  current_VH  = mean(VH_dB) over the same window
  delta_VV    = current_VV - baseline_VV
  delta_VH    = current_VH - baseline_VH
  mask        = (delta_VV >= threshold_db) AND (delta_VH >= threshold_db)

Returns a stacked xarray with three bands: delta_vv, delta_vh, mask (uint8).

MPC's sentinel-1-rtc collection delivers linear-power gamma-naught (not dB);
we convert via 10*log10 BEFORE averaging because dB averaging is mathematically
different (and what Forkuor reports). NaN-safe means are used because not every
acquisition covers every pixel (orbit gaps).

Compute strategy:
  - stackstac lazy-loads into dask-backed xarray
  - We .persist() the temporal reductions so MPC asset reads happen up-front
    (before signed URLs expire ~1h after sign_inplace).
  - resolution=20 m matches the native RTC pixel size; epsg=32630 is UTM zone
    30N which covers all of Ghana with minimal distortion.
"""

import re
from datetime import date, timedelta
from typing import cast

import numpy as np
import stackstac
import structlog
import xarray as xr
from pystac import Item

log = structlog.get_logger()

GHANA_UTM_EPSG = 32630
NATIVE_RES_M = 20
DASK_CHUNK_PX = 2048


def _stack(items: list[Item], bbox: tuple[float, float, float, float]) -> xr.DataArray:
    """Lazy-stack Sentinel-1 RTC items into a (time, band, y, x) DataArray.

    dtype=float64 is forced because stackstac 0.5.1 refuses float32 with the
    default nan fill_value. The doubled memory (~8 GB for full Ghana vs ~4 GB)
    fits comfortably in the 16 GB GitHub Actions runner.

    errors_as_nodata swallows transient Azure Blob partial-read errors as NaN.
    With 100+ scenes averaged together, losing one chunk per scene is
    statistical noise; aborting the whole compute on a TIFFFillTile short read
    would be far worse. The patterns cover the actual error strings observed
    against MPC's sentinel-1-rtc blobs (TIFFFillTile + Azure 5xx).
    """
    stack = stackstac.stack(
        items,
        assets=["vv", "vh"],
        bounds_latlon=bbox,
        epsg=GHANA_UTM_EPSG,
        resolution=NATIVE_RES_M,
        chunksize=(-1, 1, DASK_CHUNK_PX, DASK_CHUNK_PX),
        dtype="float64",
        rescale=False,
        errors_as_nodata=(
            re.compile(r"TIFFFillTile|TIFFReadEncodedTile|HTTP response code|Read failed"),
        ),
    )
    return cast(xr.DataArray, stack)


def _linear_to_db(da: xr.DataArray) -> xr.DataArray:
    """Convert linear-power gamma-naught to dB, masking zeros first.

    RTC pixels with no valid data are encoded as 0 (not NaN) by MPC. log10(0) is
    -inf which corrupts later means; mask them to NaN before the conversion.
    """
    valid = da.where(da > 0)
    return 10.0 * cast(xr.DataArray, np.log10(valid))


def compute_delta(
    items_baseline: list[Item],
    items_current: list[Item],
    bbox: tuple[float, float, float, float],
    threshold_db: float,
) -> xr.Dataset:
    """Return a Dataset with delta_vv, delta_vh, mask bands for the bbox."""

    baseline = _linear_to_db(_stack(items_baseline, bbox)).mean(
        dim="time", skipna=True
    )
    current = _linear_to_db(_stack(items_current, bbox)).mean(
        dim="time", skipna=True
    )

    # Persist the temporal reductions to materialise MPC reads up front.
    # Without this, the actual reads (and signed-URL validation) happen during
    # the mask-write later -- past the sign_inplace TTL on long runs.
    baseline = baseline.persist()
    current = current.persist()

    # delta indexed by band ('vv','vh') with shape (band, y, x).
    delta = current - baseline

    delta_vv = delta.sel(band="vv")
    delta_vh = delta.sel(band="vh")

    mask = ((delta_vv >= threshold_db) & (delta_vh >= threshold_db)).astype("uint8")

    # NaN propagation: if either polarisation has no baseline OR no current
    # observation, the mask is 0 (not 1). That's fine -- absent data should
    # not produce a detection.
    mask = mask.fillna(0).astype("uint8")

    ds = xr.Dataset(
        {
            "delta_vv": delta_vv.astype("float32"),
            "delta_vh": delta_vh.astype("float32"),
            "mask": mask,
        }
    )

    n_baseline = len(items_baseline)
    n_current = len(items_current)
    log.info(
        "Computed delta",
        n_baseline_scenes=n_baseline,
        n_current_scenes=n_current,
        threshold_db=threshold_db,
        out_shape=tuple(ds["mask"].shape),
    )
    return ds


def baseline_window(period_start: date, baseline_months: int) -> tuple[date, date]:
    """Return (start, end) for the trailing baseline window ending the day
    BEFORE period_start.

    The day-before-end is non-negotiable: STAC datetime ranges are inclusive,
    so if baseline_end == period_start the Day 1 acquisitions would contribute
    to BOTH the baseline mean AND the current mean, compressing the delta
    toward zero on Day 1 and biasing the detector toward false negatives.
    """
    end = period_start - timedelta(days=1)
    y, m = period_start.year, period_start.month - baseline_months
    while m <= 0:
        m += 12
        y -= 1
    start = date(y, m, 1)
    return start, end
