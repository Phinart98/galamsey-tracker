"""Score each disturbance cluster for signs of mining, using only automatic evidence.

Evidence, strongest first:
  new water   OPERA DSWx-S1 (radar, sees through cloud) shows water at or beside the
              cluster in the recent window that was not water in the same window a year
              earlier. Galamsey pits fill with water; farm clearings do not.
  known mine  within 500 m of mining mapped by Barenblitt et al. (2019 extent).
  river       within 300 m of a major river centreline (OSM). Pits follow rivers.

Bands:
  strong      at least 0.18 ha (2 pixels) of new water, or new water plus known mining nearby
  some        any new water, or known mining nearby, or beside a river
  unclear     none of the above: the plants are gone but nothing points to mining
"""
import datetime as dt
import sys

import geopandas as gpd
import numpy as np
import rasterio
import requests
from rasterio.features import rasterize
from scipy import ndimage

from forkuor import GDAL_ENV

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
WATER = (1,)              # DSWx-S1 B01_WTR: 1 = open water. 0 = not water; 250+ = masked or fill.
NEAR_WATER_M = 60
KNOWN_MINE_M = 500
RIVER_M = 300
STRONG_NEW_WATER_HA = 0.18


def wtr_urls(tile, start, end):
    r = requests.get(CMR, params={"short_name": "OPERA_L3_DSWX-S1_V1", "producer_granule_id": f"*{tile}*",
                                  "options[producer_granule_id][pattern]": "true",
                                  "temporal": f"{start}T00:00:00Z,{end}T23:59:59Z", "page_size": 200})
    r.raise_for_status()
    return [l["href"] for g in r.json()["feed"]["entry"] for l in g["links"]
            if l["href"].startswith("https") and l["href"].endswith("_B01_WTR.tif")]


def water_count(urls, shape_, transform):
    """Per pixel: how many acquisitions saw open water, and how many saw the pixel at all."""
    seen = np.zeros(shape_, np.uint16)
    wet = np.zeros(shape_, np.uint16)
    for u in urls:
        with rasterio.open("/vsicurl/" + u) as src:
            if src.shape != shape_ or src.transform != transform:
                continue  # DSWx-S1 shares the MGRS grid with DIST-HLS; skip anything that does not
            a = src.read(1)
        valid = a < 250
        seen += valid
        wet += valid & np.isin(a, WATER)
    return wet, seen


def new_water_mask(tile, data_date, shape_, transform, window_days=60):
    end = dt.date.fromisoformat(data_date)
    start = end - dt.timedelta(days=window_days)
    then_end, then_start = end.replace(year=end.year - 1), start.replace(year=start.year - 1)
    with rasterio.Env(**GDAL_ENV):
        now_wet, now_seen = water_count(wtr_urls(tile, start, end), shape_, transform)
        old_wet, old_seen = water_count(wtr_urls(tile, then_start, then_end), shape_, transform)
    # Water now in at least 2 looks, never water a year ago, and actually observed a year ago.
    return (now_wet >= 2) & (old_wet == 0) & (old_seen >= 2)


def score(clusters, new_water, transform, rivers, known_mines):
    px_ha = abs(transform.a * transform.e) / 1e4
    near = ndimage.binary_dilation(new_water, iterations=max(1, NEAR_WATER_M // 30))
    nw_ha = []
    for geom in clusters.geometry:
        m = rasterize([(geom.buffer(NEAR_WATER_M), 1)], out_shape=new_water.shape, transform=transform, dtype="uint8").astype(bool)
        nw_ha.append(float((m & near & new_water).sum()) * px_ha)
    out = clusters.copy()
    out["new_water_ha"] = np.round(nw_ha, 2)
    out["near_known_mine"] = out.geometry.distance(known_mines.union_all()) <= KNOWN_MINE_M
    out["near_river"] = out.geometry.distance(rivers.union_all()) <= RIVER_M
    has_water = out.new_water_ha > 0
    strong = (out.new_water_ha >= STRONG_NEW_WATER_HA) | (has_water & out.near_known_mine)
    some = has_water | out.near_known_mine | out.near_river
    out["signs"] = np.where(strong, "strong", np.where(some, "some", "unclear"))
    return out


if __name__ == "__main__":
    import warnings; warnings.filterwarnings("ignore")
    from clusters import load_clusters
    tile = sys.argv[1] if len(sys.argv) > 1 else "T30NXM"
    clusters = gpd.read_file("data/clusters_30NXM.gpkg")
    with rasterio.open("data/dist/VEG-DIST-STATUS.tif") as s:
        shape_, transform = s.shape, s.transform
    _, data_date = load_clusters()
    nw = new_water_mask(tile, data_date, shape_, transform)
    print(f"new water pixels in tile: {nw.sum():,} ({nw.sum()*0.09:,.0f} ha)")
    rivers = gpd.read_file("data/osm/rivers.gpkg").to_crs(clusters.crs)
    mines = gpd.read_file("data/barenblitt/FullConversiontoMiningExtent2019/FullConversiontoMiningExtent2019.shp").to_crs(clusters.crs)
    scored = score(clusters, nw, transform, rivers, mines)
    scored.to_file("data/clusters_30NXM.gpkg")
    print(scored.head(10)[["id", "ha", "licence", "new_water_ha", "near_known_mine", "near_river", "signs"]].to_string(index=False))
    t = scored.groupby(["signs", "licence"]).ha.sum().unstack(fill_value=0).round(0)
    print("\nhectares by mining signs (rows) and licence (columns)\n", t.to_string())
