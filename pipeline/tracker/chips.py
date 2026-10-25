"""Before/after Sentinel-2 true-colour images of a place, small enough for phones on prepaid data."""
import datetime as dt
import io
import time

import numpy as np
import rasterio
from PIL import Image
from pystac_client import Client
from rasterio.errors import RasterioIOError
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

EARTH_SEARCH = "https://earth-search.aws.element84.com/v1"
# c1-l2a (reprocessed) has almost nothing before 2019, so older dates fall back to l2a
COLLECTIONS = ("sentinel-2-c1-l2a", "sentinel-2-l2a")
CLOUDY_SCL = (3, 8, 9, 10)   # cloud shadow, medium and high cloud probability, thin cirrus
MAX_CLOUD = 0.10
MAX_NODATA = 0.02
WIDTHS = (360, 720)
# A stalled read with no timeout hung a local run for 85 minutes (2026-10-25). Every read now gives
# up after a minute, and each place gets a few minutes before it waits for next week's retry.
HTTP = {"GDAL_HTTP_TIMEOUT": "60", "GDAL_HTTP_CONNECTTIMEOUT": "20", "GDAL_HTTP_MAX_RETRY": "2",
        "GDAL_HTTP_RETRY_DELAY": "5", "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR"}
PLACE_BUDGET_S = 180
# The scene cloud mask misses thick haze and broken cloud. Those look bright and grey, while mining
# ground is bright but yellow or orange. Measured on 120 images: clear ones score 0 to 0.13 (grey
# tailings), cloudy ones 0.22 (broken cloud), 0.34 and 0.91 (fog) (spike log section 14).
MAX_GREY = 0.18


def usable_chip(scl: np.ndarray) -> bool:
    nodata = float((scl == 0).mean())
    cloudy = float(np.isin(scl, CLOUDY_SCL).mean())
    return nodata <= MAX_NODATA and cloudy <= MAX_CLOUD + 1e-9


def hazy(rgb: np.ndarray) -> bool:
    v = rgb.astype(np.int16)
    low = v.min(axis=2)
    grey = (low >= 90) & (v.max(axis=2) - low < 35)
    return float(grey.mean()) > MAX_GREY


def _bbox(lon: float, lat: float, half_km: float) -> list[float]:
    d = half_km / 111.32
    return [lon - d, lat - d, lon + d, lat + d]


def _read(href: str, bbox: list[float]) -> np.ndarray:
    with rasterio.Env(**HTTP), rasterio.open(href) as src:
        b = transform_bounds(4326, src.crs, *bbox)
        return src.read(window=from_bounds(*b, src.transform), boundless=True, fill_value=0)


def clearest(lon: float, lat: float, half_km: float, start: dt.date, end: dt.date, max_items: int = 40):
    """The least cloudy usable true-colour crop between start and end, as (date, HxWx3 uint8) or None."""
    deadline = time.monotonic() + PLACE_BUDGET_S
    bbox = _bbox(lon, lat, half_km)
    cat = Client.open(EARTH_SEARCH, timeout=60)
    items = [i for c in COLLECTIONS
             for i in cat.search(collections=[c], bbox=bbox, datetime=f"{start}/{end}",
                                 query={"eo:cloud_cover": {"lt": 30}}, max_items=max_items).items()]
    for item in sorted(items, key=lambda i: i.properties.get("eo:cloud_cover", 100)):
        if time.monotonic() > deadline:
            return None
        rgb = scene(item, bbox)
        if rgb is not None:
            return item.datetime.date(), rgb
    return None


def scene(item, bbox: list[float]) -> np.ndarray | None:
    """The true-colour crop of one scene, or None if it is cloudy, hazy, has gaps or cannot be read."""
    try:
        if not usable_chip(_read(item.assets["scl"].href, bbox)[0]):
            return None
        rgb = np.moveaxis(_read(item.assets["visual"].href, bbox), 0, -1)
    except RasterioIOError:  # a broken file on Earth Search once ended a whole run (2026-10-25)
        return None
    if (rgb.sum(axis=2) == 0).mean() > MAX_NODATA or hazy(rgb):
        return None
    return rgb


def encode(rgb: np.ndarray) -> dict[str, bytes]:
    """AVIF and WebP at each width, keyed like '360.avif'."""
    out = {}
    img = Image.fromarray(rgb)
    for w in WIDTHS:
        resized = img.resize((w, round(img.height * w / img.width)), Image.LANCZOS)
        for fmt, opts in (("avif", {"quality": 55}), ("webp", {"quality": 72})):
            buf = io.BytesIO()
            resized.save(buf, format=fmt.upper(), **opts)
            out[f"{w}.{fmt}"] = buf.getvalue()
    return out
