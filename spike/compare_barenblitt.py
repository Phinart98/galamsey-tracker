"""Spatial agreement between Forkuor-style detections and Barenblitt et al. 2021 mining polygons."""
import sys, numpy as np, rasterio, geopandas as gpd
from rasterio.features import rasterize
from shapely.geometry import box

diff_path, threshold = sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 1.65
with rasterio.open(diff_path) as src:
    d, T, shape, bounds = src.read(1), src.transform, src.shape, src.bounds
aoi = box(*bounds)

annual = gpd.read_file("data/barenblitt/MiningConversion_2007-2017Vec/MiningConversion_2007-2017Vec.shp").to_crs(32630)
extent = gpd.read_file("data/barenblitt/FullConversiontoMiningExtent2019/FullConversiontoMiningExtent2019.shp").to_crs(32630)
annual, extent = annual[annual.intersects(aoi)], extent[extent.intersects(aoi)]

def mask(geoms):
    return rasterize(((g, 1) for g in geoms), out_shape=shape, transform=T, fill=0, dtype="uint8").astype(bool)

mined_by_2017 = mask(annual.geometry)
mined_by_2019 = mask(extent.geometry) | mined_by_2017
new_2018_19 = mined_by_2019 & ~mined_by_2017
valid = np.isfinite(d)
px = 30 * 30 / 1e4  # ha

for label, det in [("rise >= +%.2f dB" % threshold, d >= threshold), ("fall <= -%.2f dB" % threshold, d <= -threshold),
                   ("either direction", np.abs(d) >= threshold)]:
    det &= valid
    hit_new = (det & new_2018_19).sum()
    print(f"\n{label}: detected {det.sum()*px:,.0f} ha")
    print(f"  inside Barenblitt new 2018-19 mining : {hit_new*px:,.0f} ha  "
          f"(recall of new mining {hit_new/max(new_2018_19.sum(),1):.0%})")
    print(f"  inside any Barenblitt mining by 2019 : {(det & mined_by_2019).sum()*px:,.0f} ha "
          f"(precision vs all mining {(det & mined_by_2019).sum()/max(det.sum(),1):.0%})")
print(f"\nBarenblitt in AOI: mined by 2017 {mined_by_2017.sum()*px:,.0f} ha, new 2018-19 {new_2018_19.sum()*px:,.0f} ha, "
      f"AOI valid {valid.mean():.0%}")
