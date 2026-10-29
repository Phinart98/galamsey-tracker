"""The "likely galamsey" reading: open water in or right next to a patch on land with no licence to mine.

Mining pits fill with water and farms rarely have ponds. Water swallows shortwave infrared light while soil
and plants reflect it, so MNDWI = (green - SWIR) / (green + SWIR) is above zero over water (Xu 2006).
Tested blind on 52 marked patches: 46 showed mining, and it marked 46 of 47 mining patches (spike log s27).
"""
import datetime as dt

import geopandas as gpd
import numpy as np
import rasterio
from pystac_client import Client
from rasterio.errors import RasterioIOError
from rasterio.features import geometry_mask
from rasterio.warp import transform_bounds, transform_geom
from rasterio.windows import from_bounds
from shapely.geometry import mapping

from tracker import refresh
from tracker.chips import COLLECTIONS, EARTH_SEARCH, HTTP

NO_LICENCE_TO_MINE = ("no licence", "prospecting only")
RING_M = 60
MAX_RING_CLOUD = 0.05
CLOUDY = (0, 3, 8, 9, 10)  # no data, cloud shadow, cloud, cirrus: as in the blind test
RETRY_DAYS = 7
WORK_CRS = "EPSG:32630"


def mndwi(green: np.ndarray, swir16: np.ndarray) -> np.ndarray:
    return (green - swir16) / (green + swir16 + 1e-6)


def water_share(bands: dict, scl: np.ndarray, near: np.ndarray) -> float | None:
    """Share of the ring's pixels that are open water, or None if cloud or gaps cover more than 5% of it."""
    if np.isin(scl[near], CLOUDY).mean() > MAX_RING_CLOUD:
        return None
    return round(float((mndwi(bands["green"], bands["swir16"])[near] > 0).mean()), 3)


def needs_reading(rec: dict, today: dt.date) -> bool:
    if not rec.get("active") or rec.get("licence") not in NO_LICENCE_TO_MINE:
        return False
    s = rec.get("signs")
    if not s:
        return True
    if s.get("missing"):
        return (today - dt.date.fromisoformat(s["checked"])).days >= RETRY_DAYS
    return refresh.due(s, rec, s["scene"], today)


def likely_galamsey(licence: str, water: float | None) -> bool:
    return licence in NO_LICENCE_TO_MINE and water is not None and water > 0


def _read(href: str, bounds_ll, shape=None):
    with rasterio.Env(**HTTP), rasterio.open(href) as src:
        win = from_bounds(*transform_bounds(4326, src.crs, *bounds_ll), src.transform)
        data = src.read(1, window=win, boundless=True, fill_value=0, out_shape=shape)
        return data, src.window_transform(win), src.crs


def _scene_reading(item, poly_ll) -> dict | None:
    """Measured the same way as the blind test (spike/signs_features.py): every band on the 10 m green grid."""
    ring = gpd.GeoSeries([poly_ll], crs=4326).to_crs(WORK_CRS).buffer(RING_M).to_crs(4326).iloc[0]
    try:
        green, transform, crs = _read(item.assets["green"].href, ring.bounds)
        swir16 = _read(item.assets["swir16"].href, ring.bounds, green.shape)[0]
        scl = _read(item.assets["scl"].href, ring.bounds, green.shape)[0]
    except (RasterioIOError, KeyError):
        return None
    near = ~geometry_mask([transform_geom(4326, crs, mapping(ring))], green.shape, transform)
    if near.sum() < 5:
        return None
    water = water_share({"green": green.astype("float32"), "swir16": swir16.astype("float32")}, scl, near)
    return None if water is None else {"water": water, "scene": str(item.datetime.date())}


def reading(poly_ll, first_seen: str, today: dt.date, tries: int = 12) -> dict | None:
    """The water reading from the clearest scene since the patch was first seen, or None if none is clear."""
    bbox = list(poly_ll.buffer(0.002).bounds)
    cat = Client.open(EARTH_SEARCH, timeout=60)
    items = [i for c in COLLECTIONS for i in cat.search(collections=[c], bbox=bbox, datetime=f"{first_seen}/{today}",
                                                         query={"eo:cloud_cover": {"lt": 30}}, max_items=30).items()]
    for item in sorted(items, key=lambda i: i.properties.get("eo:cloud_cover", 100))[:tries]:
        r = _scene_reading(item, poly_ll)
        if r:
            return r
    return None
