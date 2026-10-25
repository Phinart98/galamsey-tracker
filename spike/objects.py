"""Object-level agreement: clusters of detected pixels vs Barenblitt polygons (buffered 60 m)."""
import sys, numpy as np, rasterio, geopandas as gpd
from scipy import ndimage
from rasterio.features import rasterize
from shapely.geometry import box
diff_path, thr = sys.argv[1], 1.65
with rasterio.open(diff_path) as s: d, T, shp, b = s.read(1), s.transform, s.shape, s.bounds
aoi = box(*b)
ext = gpd.read_file("data/barenblitt/FullConversiontoMiningExtent2019/FullConversiontoMiningExtent2019.shp").to_crs(32630)
ext = ext[ext.intersects(aoi)]
near_mine = rasterize(((g, 1) for g in ext.buffer(60)), out_shape=shp, transform=T, fill=0, dtype="uint8").astype(bool)
mine_lbl, n_mines = ndimage.label(rasterize(((g, 1) for g in ext.geometry), out_shape=shp, transform=T, fill=0, dtype="uint8"))
for name, det in [("rise", d >= thr), ("fall", d <= -thr), ("either", np.abs(d) >= thr)]:
    lbl, n = ndimage.label(det)
    sizes = ndimage.sum(det, lbl, range(1, n + 1)) * 0.09  # ha
    hit = ndimage.maximum(near_mine, lbl, range(1, n + 1)).astype(bool)
    for min_ha in (0.5, 2, 5):
        k = sizes >= min_ha
        found = np.unique(mine_lbl[np.isin(lbl, np.flatnonzero(k) + 1) & (mine_lbl > 0)])
        print(f"{name:6} clusters>={min_ha:>3} ha: {k.sum():5} clusters, {sizes[k].sum():7,.0f} ha | "
              f"{hit[k].mean():.0%} touch Barenblitt mining | mines found {len(found)}/{n_mines}")
