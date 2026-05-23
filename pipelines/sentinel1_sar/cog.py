"""Write the (delta_vv, delta_vh, mask) Dataset as a 3-band Cloud Optimised
GeoTIFF and upload it to Cloudflare R2.

We bypass rio_cogeo.cog_translate (which expects a source file) and use its
lower-level cog_profiles + rasterio direct write so we don't need an
intermediate temp .tif. xarray's .rio.to_raster supports the COG driver
directly in rasterio>=1.3.
"""

import gc
import os
from pathlib import Path
from typing import Any

import boto3
import numpy as np
import rasterio
import structlog
import xarray as xr
from botocore.config import Config
from rasterio.transform import Affine
from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles

log = structlog.get_logger()

# stackstac's output CRS is always set from the `epsg` argument we pass in
# threshold.py (GHANA_UTM_EPSG = 32630). We bind it here to a constant rather
# than reading `ds.rio.crs` because rioxarray is not in the pipeline's
# dependencies — the accessor would never be registered and the branch was
# silently dead. Single source of truth across modules.
OUTPUT_EPSG = 32630


def _affine_from_xarray(ds: xr.Dataset) -> Affine:
    """Build a rasterio Affine from an xarray Dataset with x/y coords.

    stackstac emits north-up rasters: y descends, x ascends. The Affine is
    constructed from the corner coordinates and pixel sizes.
    """
    xs = ds["x"].values
    ys = ds["y"].values
    px = float(xs[1] - xs[0])
    py = float(ys[1] - ys[0])  # negative for north-up
    # Top-left corner is the centre of the first pixel shifted half a pixel
    # up-and-left.
    return Affine.translation(xs[0] - px / 2, ys[0] - py / 2) * Affine.scale(px, py)


def write_cog(ds: xr.Dataset, out_path: Path) -> Path:
    """Materialise the dask-backed Dataset and write a 3-band COG to disk.

    Memory strategy: we compute each band SEQUENTIALLY, write it, then drop
    the reference and call gc.collect(). For full Ghana (~30k x 35k px), each
    float32 band is ~4 GB, so holding all three plus dask buffers would peak
    near 16 GB and OOM the GitHub Actions runner. Band-by-band keeps peak
    resident around 4-5 GB.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    transform = _affine_from_xarray(ds)
    crs = f"EPSG:{OUTPUT_EPSG}"

    height = int(ds.sizes["y"])
    width = int(ds.sizes["x"])

    # First write a non-COG GeoTIFF to a sibling temp path; cog_translate
    # then rewrites it as a proper COG with overviews.
    tmp_path = out_path.with_suffix(".tmp.tif")
    with rasterio.open(
        tmp_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=3,
        dtype="float32",
        crs=crs,
        transform=transform,
        nodata=float("nan"),
    ) as dst:
        # Bands: 1=delta_vv, 2=delta_vh, 3=mask (cast to float32 NaN/1.0 so a
        # single dtype simplifies downstream readers; the mask round-trips
        # cleanly because uint8 0/1 -> float32 0.0/1.0 is exact).
        for band_idx, name in enumerate(["delta_vv", "delta_vh", "mask"], start=1):
            arr = ds[name].compute().values.astype("float32")
            dst.write(arr, band_idx)
            dst.set_band_description(band_idx, {
                "delta_vv": "delta_vv_db",
                "delta_vh": "delta_vh_db",
                "mask": "change_mask",
            }[name])
            del arr
            gc.collect()

    cog_profile: dict[str, Any] = cog_profiles.get("deflate")  # type: ignore[no-untyped-call]
    cog_profile.update({"blockxsize": 512, "blockysize": 512})
    cog_translate(
        tmp_path,
        out_path,
        cog_profile,
        in_memory=False,
        quiet=True,
        web_optimized=False,
        overview_resampling="average",
    )
    tmp_path.unlink(missing_ok=True)

    log.info("Wrote COG", path=str(out_path), bytes=out_path.stat().st_size)
    return out_path


def upload_to_r2(local_path: Path, key: str) -> str:
    """Upload `local_path` to R2 under `key`. Returns the public URL."""
    account_id = os.environ["R2_ACCOUNT_ID"]
    bucket = os.environ.get("R2_BUCKET", "galamsey-static")
    endpoint_url = (
        os.environ.get("R2_ENDPOINT_URL")
        or f"https://{account_id}.r2.cloudflarestorage.com"
    )
    # Path-style addressing is non-negotiable for R2: virtual-host style (the
    # boto3 default) sends Host: bucket.account.r2.cloudflarestorage.com which
    # R2 only accepts for DNS-compliant bucket names. Path-style routes via
    # endpoint/bucket/key, which works for any bucket name R2 lets you create.
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(s3={"addressing_style": "path"}),
    )
    s3.upload_file(
        str(local_path),
        bucket,
        key,
        ExtraArgs={
            "ContentType": "image/tiff",
            "CacheControl": "public, max-age=86400",
        },
    )
    public_base = os.environ.get(
        "R2_PUBLIC_BASE_URL", f"https://{bucket}.{account_id}.r2.dev"
    ).rstrip("/")
    url = f"{public_base}/{key}"
    log.info("Uploaded to R2", bucket=bucket, key=key, url=url)
    return url


def array_stats(arr: "np.ndarray") -> dict[str, float]:
    """Helper for dry-run logging: simple stats over the mask/delta bands."""
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return {"count": 0.0, "mean": float("nan"), "max": float("nan")}
    return {
        "count": float(finite.size),
        "mean": float(finite.mean()),
        "max": float(finite.max()),
    }
