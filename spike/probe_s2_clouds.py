"""Scene-level cloud statistics for Sentinel-2 L2A over the southern Ghana mining belt (Earth Search STAC)."""
import collections
from pystac_client import Client

# Tiles covering Amansie/Offin, Wassa Amenfi, Pra basin
TILES = ["30NWM", "30NVM", "30NWN", "30NVL"]
cat = Client.open("https://earth-search.aws.element84.com/v1")
rows = collections.defaultdict(lambda: [0, 0, 0])  # month -> [scenes, <30% cloud, <10% cloud]
for tile in TILES:
    items = cat.search(collections=["sentinel-2-c1-l2a"], datetime="2023-01-01/2026-10-24",
                       query={"grid:code": {"eq": f"MGRS-{tile}"}}, max_items=5000).items()
    for it in items:
        m = it.datetime.strftime("%m")
        cc = it.properties.get("eo:cloud_cover", 100)
        r = rows[m]; r[0] += 1; r[1] += cc < 30; r[2] += cc < 10
names = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
print("month  scenes  <30%cloud  <10%cloud   (4 tiles, 2023-2026, scenes per tile per month in brackets)")
for m in sorted(rows):
    s, a, b = rows[m]; yrs = 4 if m <= "10" else 3
    print(f"{names[int(m)-1]:5} {s:6} {a:9} {b:9}   ({a/len(TILES)/yrs:.1f} / {b/len(TILES)/yrs:.1f})")
