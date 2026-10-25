"""Probe NASA CMR for OPERA products over the southern Ghana mining belt."""
import requests, collections, datetime as dt

BBOX = "-3.2,5.0,-0.5,7.5"  # lon_min,lat_min,lon_max,lat_max
CMR = "https://cmr.earthdata.nasa.gov/search"

def find_collections(keyword):
    r = requests.get(f"{CMR}/collections.json", params={"keyword": keyword, "page_size": 50})
    r.raise_for_status()
    return [(c["short_name"], c.get("version_id"), c["id"], c.get("archive_center")) for c in r.json()["feed"]["entry"]]

for kw in []:
    print("==", kw)
    for c in find_collections(kw):
        print("  ", c)

def granules(short_name, start, end, max_pages=20):
    out, headers = [], {}
    for _ in range(max_pages):
        r = requests.get(f"{CMR}/granules.json", headers=headers, params={
            "short_name": short_name, "bounding_box": BBOX,
            "temporal": f"{start},{end}", "page_size": 2000, "sort_key": "-start_date"})
        r.raise_for_status()
        e = r.json()["feed"]["entry"]
        out += e
        sa = r.headers.get("CMR-Search-After")
        if not sa or not e: break
        headers = {"CMR-Search-After": sa}
    return out

import sys
for sn in sys.argv[1:]:
    g = granules(sn, "2026-09-01T00:00:00Z", "2026-10-25T00:00:00Z")
    print(f"\n## {sn}: {len(g)} granules since 2026-09-01")
    days = collections.Counter(x["time_start"][:10] for x in g)
    print("  acquisition days:", sorted(days)[-12:])
    lat = []
    for x in g[:200]:
        t0 = dt.datetime.fromisoformat(x["time_start"].replace("Z","+00:00"))
        t1 = dt.datetime.fromisoformat(x["updated"].replace("Z","+00:00")) if "updated" in x else None
        if t1: lat.append((t1 - t0).total_seconds()/3600)
    if lat:
        lat.sort(); print(f"  latency h (updated-start) min {lat[0]:.1f} median {lat[len(lat)//2]:.1f} max {lat[-1]:.1f}")
    if g: print("  example:", g[0]["title"])
