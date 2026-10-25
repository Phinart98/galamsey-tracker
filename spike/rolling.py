"""Same-method trend: land newly cleared in the 12 months to the same date each year.

Uses the DIST-ALERT-HLS granule nearest a fixed date each year and counts its trailing
365 days, so the late-confirmation lag at the window end is identical every year.
DIST-ANN is avoided because its first year absorbs a backlog and its latest year is
produced before late alerts are confirmed.
"""
import datetime as dt
import glob
import sys

import numpy as np
import rasterio
import requests
from rasterio.features import rasterize
from scipy import ndimage

from forkuor import GDAL_ENV
from licences import LARGE_SCALE, NONE, PROSPECTING, SMALL_SCALE, load_licences

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
EPOCH = dt.date(2020, 12, 31)
CLASS_CODE = {PROSPECTING: 1, SMALL_SCALE: 2, LARGE_SCALE: 3}


def granule_near(bbox, day, tile):
    """Latest DIST-ALERT granule for the tile acquired within the 10 days up to `day`."""
    start = day - dt.timedelta(days=10)
    r = requests.get(CMR, params={"short_name": "OPERA_L3_DIST-ALERT-HLS_V1", "bounding_box": bbox,
                                  "temporal": f"{start}T00:00:00Z,{day}T23:59:59Z", "page_size": 100,
                                  "sort_key": "-start_date"})
    r.raise_for_status()
    for g in r.json()["feed"]["entry"]:
        if f"_{tile}_" in g["title"]:
            links = {l["href"].split(g["title"])[-1]: l["href"] for l in g["links"] if l["href"].startswith("https")}
            return g["title"], links["_VEG-DIST-STATUS.tif"], links["_VEG-DIST-DATE.tif"]
    return None


def trailing_year(status, date, end_day):
    end = (end_day - EPOCH).days
    hit = np.isin(status, [6, 8]) & (date > end - 365) & (date <= end)
    labels, n = ndimage.label(hit, structure=np.ones((3, 3)))
    sizes = ndimage.sum(hit, labels, range(1, n + 1))
    return np.isin(labels, np.flatnonzero(sizes >= 1 / 0.09) + 1)


if __name__ == "__main__":
    import warnings; warnings.filterwarnings("ignore")
    tile, bbox = "T30NXM", "-2.0,5.8,-1.9,5.9"
    month_day = sys.argv[1] if len(sys.argv) > 1 else "10-22"
    licences, _ = load_licences(sorted(glob.glob("data/licences/*.geojson"))[-1])
    with rasterio.Env(**GDAL_ENV):
        for year in (2024, 2025, 2026):
            day = dt.date.fromisoformat(f"{year}-{month_day}")
            g = granule_near(bbox, day, tile)
            if not g:
                print(year, "no granule"); continue
            title, s_url, d_url = g
            with rasterio.open("/vsicurl/" + s_url) as s:
                status, transform, crs, shape_ = s.read(1), s.transform, s.crs, s.shape
            with rasterio.open("/vsicurl/" + d_url) as s:
                date = s.read(1).astype(int)
            gdate = dt.date.fromisoformat(f"{title.split('_')[4][:4]}-{title.split('_')[4][4:6]}-{title.split('_')[4][6:8]}")
            patches = trailing_year(status, date, gdate)
            lic = licences.to_crs(crs); code = np.zeros(shape_, np.uint8)
            for cls in (PROSPECTING, SMALL_SCALE, LARGE_SCALE):
                part = lic[lic.cls == cls]
                if len(part):
                    code[rasterize(((x, 1) for x in part.geometry), out_shape=shape_, transform=transform, dtype="uint8") == 1] = CLASS_CODE[cls]
            tot = patches.sum() * 0.09
            none = (patches & (code == 0)).sum() * 0.09
            print(f"12 months to {gdate}: {tot:,.0f} ha, no licence {none:,.0f} ha ({none/tot:.0%}), statuses {dict(zip(*[a.tolist() for a in np.unique(status, return_counts=True)]))}", flush=True)
