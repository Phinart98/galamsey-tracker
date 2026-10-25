"""Sentinel-2 true-colour before/after chips for a place, picking the clearest dry-season scene each period."""
import sys, numpy as np, rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
from pystac_client import Client
from PIL import Image

name, lon, lat, half_km = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
periods = sys.argv[5:]  # e.g. 2016-12-01/2017-02-28 2025-12-01/2026-02-28
d = half_km / 111
bbox = [lon - d, lat - d, lon + d, lat + d]
cat = Client.open("https://earth-search.aws.element84.com/v1")
chips = []
for per in periods:
    # c1-l2a (reprocessed) is sparse before 2019, so fall back to the older l2a collection
    items = sorted((i for c in ["sentinel-2-c1-l2a", "sentinel-2-l2a"]
                    for i in cat.search(collections=[c], bbox=bbox, datetime=per,
                                        query={"eo:cloud_cover": {"lt": 20}}, max_items=50).items()),
                   key=lambda i: i.properties["eo:cloud_cover"])
    for it in items:
        with rasterio.open(it.assets["visual"].href) as src:
            b = transform_bounds(4326, src.crs, *bbox)
            a = src.read(window=from_bounds(*b, src.transform), boundless=True, fill_value=0)
        if (a.sum(0) == 0).mean() < 0.02 and np.percentile(a, 90) < 200:  # full coverage, not cloud-washed
            print(per, "->", it.id, it.properties["eo:cloud_cover"], "% cloud")
            chips.append((it.datetime.date(), np.moveaxis(a, 0, -1)))
            break
img = np.concatenate([c for _, c in chips], axis=1)
Image.fromarray(img).resize((img.shape[1] * 2, img.shape[0] * 2), Image.NEAREST).save(f"data/{name}.png")
print("saved", f"data/{name}.png", [str(dte) for dte, _ in chips])
