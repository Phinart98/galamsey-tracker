"""Rank DIST-ALERT-HLS hotspots: confirmed >=50% vegetation loss in the last 12 months, clustered."""
import datetime as dt, numpy as np, rasterio, geopandas as gpd
from scipy import ndimage
from rasterio.features import rasterize
from rasterio.transform import xy
from pyproj import Transformer
EPOCH = dt.date(2020, 12, 31)  # VEG-DIST-DATE counts days from here
with rasterio.open("data/dist/VEG-DIST-STATUS.tif") as s: status, T, crs = s.read(1), s.transform, s.crs
with rasterio.open("data/dist/VEG-DIST-DATE.tif") as s: date = s.read(1).astype(int)
latest = date.max()
recent = np.isin(status, [6, 8]) & (date >= latest - 365)
lbl, n = ndimage.label(recent, structure=np.ones((3, 3)))
px_ha = 0.09
sizes = ndimage.sum(recent, lbl, range(1, n + 1)) * px_ha
ext = gpd.read_file("data/barenblitt/FullConversiontoMiningExtent2019/FullConversiontoMiningExtent2019.shp").to_crs(crs)
old_mine = rasterize(((g, 1) for g in ext.buffer(90)), out_shape=status.shape, transform=T, fill=0, dtype="uint8").astype(bool)
near_old = ndimage.maximum(old_mine, lbl, range(1, n + 1)).astype(bool)
com = ndimage.center_of_mass(recent, lbl, range(1, n + 1))
to_ll = Transformer.from_crs(crs, 4326, always_xy=True)
order = np.argsort(-sizes)
print(f"latest obs {EPOCH + dt.timedelta(int(latest))}; clusters >=1 ha: {(sizes>=1).sum()}, total {sizes[sizes>=1].sum():,.0f} ha; "
      f"{near_old[sizes>=1].mean():.0%} of them within 90 m of Barenblitt 2019 mining")
for k in order[:12]:
    r, c = com[k]; x, y = xy(T, r, c); lon, lat = to_ll.transform(x, y)
    dates = date[lbl == k + 1]
    print(f"{sizes[k]:6.1f} ha  {lat:.4f},{lon:.4f}  first {EPOCH+dt.timedelta(int(dates.min()))} last {EPOCH+dt.timedelta(int(dates.max()))}  near_old_mining={near_old[k]}")
