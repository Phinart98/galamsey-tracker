"""Year-on-year land disturbance from OPERA DIST-ANN-HLS, split by licence class.

Same rule as the weekly clusters, applied per calendar year: confirmed loss of at least
50% of plant cover (VEG-DIST-STATUS 6 or 8) first detected that year, in 8-connected
patches of at least 1 ha.
"""
import datetime as dt
import glob
import sys

import geopandas as gpd
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


def annual_granules(bbox):
    r = requests.get(CMR, params={"short_name": "OPERA_L3_DIST-ANN-HLS_V1", "bounding_box": bbox, "page_size": 50})
    r.raise_for_status()
    out = {}
    for g in r.json()["feed"]["entry"]:
        year = int(g["title"].split("_")[4])
        links = {l["href"].split(g["title"])[-1]: l["href"] for l in g["links"] if l["href"].startswith("https")}
        out[year] = (links["_VEG-DIST-STATUS.tif"], links["_VEG-DIST-DATE.tif"])
    return dict(sorted(out.items()))


def year_patches(status, date, year):
    start = (dt.date(year, 1, 1) - EPOCH).days
    end = (dt.date(year, 12, 31) - EPOCH).days
    hit = np.isin(status, [6, 8]) & (date >= start) & (date <= end)
    labels, n = ndimage.label(hit, structure=np.ones((3, 3)))
    sizes = ndimage.sum(hit, labels, range(1, n + 1))
    keep = np.flatnonzero(sizes >= 1 / 0.09) + 1  # at least 1 ha of 30 m pixels
    return np.isin(labels, keep)


if __name__ == "__main__":
    import warnings; warnings.filterwarnings("ignore")
    bbox = sys.argv[1] if len(sys.argv) > 1 else "-2.0,5.8,-1.9,5.9"  # any point inside tile 30NXM
    licences, _ = load_licences(sorted(glob.glob("data/licences/*.geojson"))[-1])
    rows = []
    with rasterio.Env(**GDAL_ENV):
        for year, (s_url, d_url) in annual_granules(bbox).items():
            with rasterio.open("/vsicurl/" + s_url) as s:
                status, transform, crs, shape_ = s.read(1), s.transform, s.crs, s.shape
            with rasterio.open("/vsicurl/" + d_url) as s:
                date = s.read(1).astype(int)
            lic = licences.to_crs(crs)
            lic_code = np.zeros(shape_, np.uint8)
            for cls in (PROSPECTING, SMALL_SCALE, LARGE_SCALE):  # later classes overwrite: most permissive wins
                part = lic[lic.cls == cls]
                if len(part):
                    m = rasterize(((g, 1) for g in part.geometry), out_shape=shape_, transform=transform, fill=0, dtype="uint8")
                    lic_code[m == 1] = CLASS_CODE[cls]
            patches = year_patches(status, date, year)
            row = {"year": year, "total_ha": round(patches.sum() * 0.09)}
            for cls, code in [(NONE, 0), *CLASS_CODE.items()]:
                row[cls] = round((patches & (lic_code == code)).sum() * 0.09)
            rows.append(row)
            print(row, flush=True)
    import pandas as pd
    df = pd.DataFrame(rows).set_index("year")
    df["no licence %"] = (df[NONE] / df.total_ha * 100).round(0)
    print(df.to_string())
    df.to_csv("data/annual_30NXM.csv")
