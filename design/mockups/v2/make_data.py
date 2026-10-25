"""Real numbers and pictures for the v2 home page mockups.

Run from the repo root: uv run --project pipeline python design/mockups/v2/make_data.py
"""
import json
import sys

import geopandas as gpd
import pandas as pd

sys.path.insert(0, "pipeline")
from tracker.run import WORK_CRS  # noqa: E402

CHIPS = "../../../pipeline/out/"
index = json.load(open("pipeline/out/places/index.json", encoding="utf-8"))
summary = json.load(open("data/summary/latest.json", encoding="utf-8"))
trend = json.load(open("data/trend.json", encoding="utf-8"))["points"]
near = pd.read_csv("pipeline/out/towns_near.csv")


def pic(rec):
    c = rec.get("chips") or {}
    if "before" not in c:
        return None
    return {"before": CHIPS + c["before"]["files"]["720.webp"], "after": CHIPS + c["after"]["files"]["720.webp"],
            "before_date": c["before"]["date"], "after_date": c["after"]["date"]}


active = [r for r in index.values() if r.get("active")]
pictured = [dict(r, pic=pic(r)) for r in active if pic(r)]

# For each of the most affected villages, the largest pictured patch within 1 km of it
patches = gpd.read_file("pipeline/out/places/latest.geojson").to_crs(WORK_CRS)
towns = gpd.read_file("pipeline/out/cache/places/settlements_ghana.geojson").to_crs(WORK_CRS)
villages, used = [], set()
for _, v in near.head(40).iterrows():
    t = towns[towns.name == v["name"]]
    if t.empty:
        continue
    ring = t.geometry.iloc[0].buffer(1000)
    ids = patches[patches.intersects(ring)].id
    # Neighbouring villages often share one big patch, so each picture is used once
    cands = sorted((index[i] for i in ids if i in index and pic(index[i]) and i not in used), key=lambda r: -r["ha"])
    if cands:
        used.add(cands[0]["id"])
        villages.append({"name": v["name"], "ha": round(v["ha"], 1), "patches": int(v["patches"]),
                         "district": cands[0].get("district"), "place_id": cands[0]["id"], "pic": pic(cands[0])})
    if len(villages) == 9:
        break

# The newest small patches are mostly farm blocks at the belt's edge, so the mockups show the largest
newest = sorted(pictured, key=lambda r: r["ha"], reverse=True)[:12]
out = {
    "data_date": summary["data_date"], "total_ha": summary["total_ha"], "patches": summary["patches"],
    "no_licence_share": summary["no_licence_to_mine"]["share"],
    "towns_within_1km": 665, "towns_5ha": 256,
    "pra": {"plant": "Daboase", "river": "Pra", "ha_upstream": 9025, "share_of_belt": 0.40, "supplies": "Sekondi-Takoradi"},
    "villages": villages,
    "newest": [{"id": r["id"], "ha": r["ha"], "near": r.get("near"), "district": r.get("district"),
                "first_seen": r["first_seen"], "licence": r["licence"], "pic": r["pic"]} for r in newest],
    "trend": [{"m": k, "ha": p["total_ha"], "settled": p["settled"]} for k, p in sorted(trend.items())],
}
json.dump(out, open("design/mockups/v2/data.json", "w", encoding="utf-8"), indent=1)
print(len(villages), "villages,", len(newest), "newest,", len(out["trend"]), "trend points")
for v in villages:
    print(" ", v["name"], v["ha"], v["district"])
