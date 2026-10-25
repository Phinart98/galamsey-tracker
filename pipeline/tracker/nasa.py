"""NASA CMR search and Earthdata-authenticated reads of OPERA DIST-ALERT-HLS granules."""
import datetime as dt
import os
import tempfile
import time

import numpy as np
import rasterio
import requests

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
DIST_ALERT = "OPERA_L3_DIST-ALERT-HLS_V1"


def gdal_env() -> dict:
    """GDAL settings so /vsicurl/ follows the Earthdata login redirect using ~/.netrc (or ~/_netrc on Windows)."""
    home = os.path.expanduser("~")
    netrc = os.environ.get("NETRC") or next(
        (p for p in (os.path.join(home, ".netrc"), os.path.join(home, "_netrc")) if os.path.exists(p)), None)
    if not netrc:
        raise RuntimeError("No Earthdata credentials: create ~/.netrc with a urs.earthdata.nasa.gov line")
    cookies = os.path.join(tempfile.gettempdir(), "edl_cookies.txt")
    return {"GDAL_HTTP_NETRC": "YES", "GDAL_HTTP_NETRC_FILE": netrc, "GDAL_HTTP_COOKIEFILE": cookies,
            "GDAL_HTTP_COOKIEJAR": cookies, "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
            "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif", "GDAL_HTTP_MAX_RETRY": "4", "GDAL_HTTP_RETRY_DELAY": "3"}


def search(short_name: str, bbox: str, start: dt.date, end: dt.date, page_size: int = 2000) -> list[dict]:
    out, headers = [], {}
    while True:
        r = requests.get(CMR, headers=headers, timeout=60, params={
            "short_name": short_name, "bounding_box": bbox, "page_size": page_size, "sort_key": "-start_date",
            "temporal": f"{start}T00:00:00Z,{end}T23:59:59Z"})
        r.raise_for_status()
        entries = r.json()["feed"]["entry"]
        out += entries
        after = r.headers.get("CMR-Search-After")
        if not after or not entries:
            return out
        headers = {"CMR-Search-After": after}


def tile_of(title: str) -> str:
    return next(p for p in title.split("_") if p.startswith("T") and len(p) == 6)


def acquired(title: str) -> dt.date:
    stamp = next(p for p in title.split("_") if len(p) == 16 and p[8] == "T")
    return dt.date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8]))


def layer_urls(entry: dict) -> dict[str, str]:
    return {l["href"].split(entry["title"])[-1].lstrip("_").removesuffix(".tif"): l["href"]
            for l in entry["links"] if l["href"].startswith("https") and l["href"].endswith(".tif")}


def latest_per_tile(bbox: str, day: dt.date, lookback_days: int = 12) -> dict[str, dict]:
    """The most recent DIST-ALERT granule for each tile acquired in the lookback window ending on `day`."""
    best: dict[str, dict] = {}
    for e in search(DIST_ALERT, bbox, day - dt.timedelta(days=lookback_days), day):
        t = tile_of(e["title"])
        if t not in best or acquired(e["title"]) > acquired(best[t]["title"]):
            best[t] = e
    return best


def read_status_and_date(entry: dict, attempts: int = 3):
    # GDAL retries HTTP errors itself but not a response cut short, which LP DAAC sends now and then
    urls = layer_urls(entry)
    for attempt in range(attempts):
        try:
            with rasterio.Env(**gdal_env()):
                with rasterio.open("/vsicurl/" + urls["VEG-DIST-STATUS"]) as s:
                    status, transform, crs = s.read(1), s.transform, s.crs
                with rasterio.open("/vsicurl/" + urls["VEG-DIST-DATE"]) as s:
                    date = s.read(1).astype(np.int32)
            return status, date, transform, crs
        except rasterio.errors.RasterioIOError:
            if attempt == attempts - 1:
                raise
            time.sleep(10 * (attempt + 1))
