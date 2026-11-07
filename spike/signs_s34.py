"""s34: does pond colour or pond count sharpen the "Likely galamsey" label? (spike log section 34)

For each patch in the three judged blind batches, re-read the scene its reading used, and measure the water
pixels within 60 m: their median red/green reflectance and how many separate ponds they form.

Run from the repo root: uv run --project pipeline python spike/signs_s34.py
"""
import json
import sys
import time

import geopandas as gpd
import numpy as np
from rasterio.errors import RasterioIOError
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom
from scipy import ndimage
from shapely.geometry import mapping

sys.path.insert(0, "pipeline")
from tracker import chips  # noqa: E402
from tracker.signs import CLOUDY, RING_M, WORK_CRS, _read, mndwi  # noqa: E402

C = "pipeline/out/checks"


def batches():
    for name in ("signs-holdout", "signs-holdout-2"):
        v = json.load(open(f"{C}/{name}/verdicts.json"))
        verdict = {n: k for k in ("mining", "not", "unclear") for n in v[k]}
        for r in json.load(open(f"{C}/{name}/readings-sealed.json")):
            if r.get("scene"):  # no clear scene: R0 marked nothing, so neither can A or B
                yield name, r["n"], r["id"], r["scene"], verdict[r["n"]]
    v = json.load(open(f"{C}/signs-holdout-3/verdicts.json"))
    for r in json.load(open(f"{C}/signs-holdout-3/readings-sealed.json")):
        if r["scenes"]:
            yield "signs-holdout-3", r["n"], r["id"], r["scenes"][0]["scene"], v[str(r["n"])]["verdict"]


def measure(poly_ll, scene):
    bbox = list(poly_ll.buffer(0.002).bounds)
    items = [i for i in chips.search(bbox, scene, scene, 5) if str(i.datetime.date()) == scene]
    if not items:
        return None
    area = gpd.GeoSeries([poly_ll], crs=4326).to_crs(WORK_CRS).buffer(RING_M).to_crs(4326).iloc[0]
    it = items[0]
    green, transform, crs = _read(it.assets["green"].href, area.bounds)
    red = _read(it.assets["red"].href, area.bounds, green.shape)[0].astype("float32")
    swir = _read(it.assets["swir16"].href, area.bounds, green.shape)[0].astype("float32")
    scl = _read(it.assets["scl"].href, area.bounds, green.shape)[0]
    green = green.astype("float32")
    near = ~geometry_mask([transform_geom(4326, crs, mapping(area))], green.shape, transform)
    water = near & (mndwi(green, swir) > 0) & ~np.isin(scl, CLOUDY)
    labels, n = ndimage.label(water, structure=np.ones((3, 3)))
    sizes = ndimage.sum(water, labels, range(1, n + 1)) if n else []
    ratio = float(np.median(red[water] / np.maximum(green[water], 1))) if water.any() else None
    return {"water_px": int(water.sum()), "ponds": int(sum(s >= 2 for s in sizes)),
            "red_green": None if ratio is None else round(ratio, 3)}


p = gpd.read_file("pipeline/out/places/latest.geojson").set_index("id")
done = {(r["batch"], r["n"]): r for r in json.load(open(f"{C}/signs-s34.json"))} if __import__("os").path.exists(f"{C}/signs-s34.json") else {}
rows = []
for batch, n, pid, scene, verdict in batches():
    if (batch, n) in done and ("water_px" in done[(batch, n)] or done[(batch, n)].get("gone")):
        rows.append(done[(batch, n)])
        continue
    row = {"batch": batch, "n": n, "id": pid, "scene": scene, "verdict": verdict}
    if pid not in p.index:
        row["gone"] = True
    else:
        for a in range(4):
            try:
                row.update(measure(p.loc[pid].geometry, scene) or {"no_scene": True})
                break
            except (RasterioIOError, OSError, Exception) as e:  # noqa: BLE001  slow link
                print("  retry", type(e).__name__, flush=True)
                time.sleep(20 * (a + 1))
    rows.append(row)
    print(row, flush=True)
    json.dump(rows, open(f"{C}/signs-s34.json", "w"), indent=1)
