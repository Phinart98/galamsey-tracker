"""PostGIS row -> GeoJSON FeatureCollection helper.

Convention: every spatial query selects the geometry as
  ST_AsGeoJSON(geom) AS geom_geojson
so this helper finds it under that key by default.
"""

import json
from typing import Any


def rows_to_feature_collection(
    rows: list[dict[str, Any]],
    geom_col: str = "geom_geojson",
    id_col: str = "id",
) -> dict[str, Any]:
    features = []
    for r in rows:
        g = r.pop(geom_col, None)
        if g is None:
            continue
        geometry = json.loads(g) if isinstance(g, str) else g
        features.append({
            "type": "Feature",
            "id": r.get(id_col),
            "geometry": geometry,
            "properties": {k: v for k, v in r.items() if k != id_col},
        })
    return {"type": "FeatureCollection", "features": features}
