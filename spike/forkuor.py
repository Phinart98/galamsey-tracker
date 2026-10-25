"""Forkuor et al. 2020 reproduction on OPERA RTC-S1.

Annual minimum of VH backscatter (dB) per pixel, one fixed track at a fixed
12-day spacing so every year has the same number of samples (the annual
minimum drops as sample count rises, which would otherwise fake change when
Sentinel-1B joined in 2017-18 and died in Dec 2021).
"""
import argparse, os, tempfile, datetime as dt
import numpy as np, requests, rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from pyproj import Transformer
from scipy.ndimage import uniform_filter

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
NETRC = os.path.expanduser("~/_netrc")
COOKIES = os.path.join(tempfile.gettempdir(), "edl_cookies.txt")
GDAL_ENV = dict(GDAL_HTTP_NETRC="YES", GDAL_HTTP_NETRC_FILE=NETRC,
                GDAL_HTTP_COOKIEFILE=COOKIES, GDAL_HTTP_COOKIEJAR=COOKIES,
                GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                GDAL_HTTP_MAX_RETRY="4", GDAL_HTTP_RETRY_DELAY="2")


def vh_granules(bbox, year, track):
    r = requests.get(CMR, params={"short_name": "OPERA_L2_RTC-S1_V1", "bounding_box": ",".join(map(str, bbox)),
                                  "temporal": f"{year}-01-01T00:00:00Z,{year}-12-31T23:59:59Z", "page_size": 2000})
    r.raise_for_status()
    by_date = {}
    for g in r.json()["feed"]["entry"]:
        if f"_{track}-" not in g["title"]:
            continue
        vh = [l["href"] for l in g["links"] if l["href"].startswith("https") and l["href"].endswith("_VH.tif")]
        if vh:
            by_date.setdefault(g["time_start"][:10], []).append(vh[0])
    return dict(sorted(by_date.items()))


def every_12_days(dates, start):
    """Keep at most one acquisition per 12-day slot, so S1A+S1B years match S1A-only years."""
    keep, seen = [], set()
    for d in dates:
        slot = (dt.date.fromisoformat(d) - start).days // 12
        if slot not in seen:
            seen.add(slot); keep.append(d)
    return keep


def grid(bbox, res=30):
    to_utm = Transformer.from_crs(4326, 32630, always_xy=True)
    x0, y0 = to_utm.transform(bbox[0], bbox[1]); x1, y1 = to_utm.transform(bbox[2], bbox[3])
    x0, y1 = res * np.floor(x0 / res), res * np.ceil(y1 / res)
    w, h = int(np.ceil((x1 - x0) / res)), int(np.ceil((y1 - y0) / res))
    return from_origin(x0, y1, res, res), w, h


def read_date(urls, transform, w, h):
    out = np.full((h, w), np.nan, np.float32)
    for u in urls:
        with rasterio.open("/vsicurl/" + u) as src, WarpedVRT(src, crs="EPSG:32630", transform=transform,
                                                             width=w, height=h, resampling=Resampling.bilinear,
                                                             src_nodata=src.nodata if src.nodata is not None else np.nan,
                                                             nodata=np.nan) as vrt:
            a = vrt.read(1).astype(np.float32)
        out = np.where(np.isnan(out), a, out)
    return out


def annual_min_db(bbox, year, track, transform, w, h):
    dates = vh_granules(bbox, year, track)
    keep = every_12_days(list(dates), dt.date(year, 1, 1))
    stack = []
    for d in keep:
        a = read_date(dates[d], transform, w, h)
        if np.isfinite(a).mean() < 0.5:
            continue
        a[a <= 0] = np.nan
        db = 10 * np.log10(a)
        valid = np.isfinite(db)
        smooth = uniform_filter(np.where(valid, db, 0), 3) / np.maximum(uniform_filter(valid.astype(float), 3), 1e-6)
        stack.append(np.where(valid, smooth, np.nan))
        print(f"  {year} {d} ok", flush=True)
    n = len(stack)
    return np.nanmin(np.stack(stack), axis=0), n


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--bbox", default="-1.80,5.90,-1.45,6.25")
    p.add_argument("--years", default="2017,2018,2019")
    p.add_argument("--track", default="T147")
    p.add_argument("--threshold", type=float, default=1.65)
    a = p.parse_args()
    bbox = [float(v) for v in a.bbox.split(",")]
    transform, w, h = grid(bbox)
    os.makedirs("data/forkuor", exist_ok=True)
    profile = dict(driver="GTiff", dtype="float32", count=1, crs="EPSG:32630", transform=transform,
                   width=w, height=h, nodata=np.nan, compress="deflate")
    mins = {}
    with rasterio.Env(**GDAL_ENV):
        for y in map(int, a.years.split(",")):
            mins[y], n = annual_min_db(bbox, y, a.track, transform, w, h)
            print(f"{y}: {n} acquisitions used")
            with rasterio.open(f"data/forkuor/min_vh_{a.track}_{y}.tif", "w", **profile) as dst:
                dst.write(mins[y], 1)
    px_km2 = 30 * 30 / 1e6
    ys = sorted(mins)
    for y0, y1 in zip(ys, ys[1:]):
        d = mins[y1] - mins[y0]
        up, down = d >= a.threshold, d <= -a.threshold
        print(f"{y0}->{y1}: +{a.threshold} dB {up.sum()*px_km2:.1f} km2 | -{a.threshold} dB {down.sum()*px_km2:.1f} km2 | valid {np.isfinite(d).mean():.0%}")
        with rasterio.open(f"data/forkuor/diff_vh_{a.track}_{y0}_{y1}.tif", "w", **profile) as dst:
            dst.write(d.astype(np.float32), 1)
