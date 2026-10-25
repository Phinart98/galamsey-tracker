"""Before/after Sentinel-2 true-colour images of a place, small enough for phones on prepaid data."""
import datetime as dt
import io

import numpy as np
import rasterio
from PIL import Image
from pystac_client import Client
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

EARTH_SEARCH = "https://earth-search.aws.element84.com/v1"
# c1-l2a (reprocessed) has almost nothing before 2019, so older dates fall back to l2a
COLLECTIONS = ("sentinel-2-c1-l2a", "sentinel-2-l2a")
CLOUDY_SCL = (3, 8, 9, 10)   # cloud shadow, medium and high cloud probability, thin cirrus
MAX_CLOUD = 0.10
MAX_NODATA = 0.02
WIDTHS = (360, 720)
# The scene cloud mask misses thick haze and broken cloud. Those look bright and grey, while mining
# ground is bright but yellow or orange. Measured on 74 images: clear ones score 0 to 0.14 (grey
# tailings), the two fogged ones 0.34 and 0.91 (spike log section 14).
MAX_GREY = 0.25


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
    with rasterio.open(href) as src:
        b = transform_bounds(4326, src.crs, *bbox)
        return src.read(window=from_bounds(*b, src.transform), boundless=True, fill_value=0)


def clearest(lon: float, lat: float, half_km: float, start: dt.date, end: dt.date, max_items: int = 40):
    """The least cloudy usable true-colour crop between start and end, as (date, HxWx3 uint8) or None."""
    bbox = _bbox(lon, lat, half_km)
    cat = Client.open(EARTH_SEARCH)
    items = [i for c in COLLECTIONS
             for i in cat.search(collections=[c], bbox=bbox, datetime=f"{start}/{end}",
                                 query={"eo:cloud_cover": {"lt": 30}}, max_items=max_items).items()]
    for item in sorted(items, key=lambda i: i.properties.get("eo:cloud_cover", 100)):
        scl = _read(item.assets["scl"].href, bbox)[0]
        if not usable_chip(scl):
            continue
        rgb = np.moveaxis(_read(item.assets["visual"].href, bbox), 0, -1)
        if (rgb.sum(axis=2) == 0).mean() > MAX_NODATA or hazy(rgb):
            continue
        return item.datetime.date(), rgb
    return None


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
