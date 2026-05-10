"""Smoke test for the alerts router.

Skipped automatically when DATABASE_URL_POOLED is not set so CI without a
live database still passes (lint + type checks remain authoritative).
"""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

REQUIRES_DB = pytest.mark.skipif(
    "DATABASE_URL_POOLED" not in os.environ,
    reason="DATABASE_URL_POOLED not set; live-DB smoke test skipped",
)


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    from main import app

    with TestClient(app) as c:
        yield c


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@REQUIRES_DB
def test_list_alerts_returns_feature_collection(client: TestClient) -> None:
    r = client.get("/alerts", params={"from": "2026-04-01", "to": "2026-05-01"})
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "FeatureCollection"
    assert isinstance(body["features"], list)
    for f in body["features"]:
        assert f["type"] == "Feature"
        assert "geometry" in f
        assert "properties" in f


@REQUIRES_DB
def test_alerts_by_region_shape(client: TestClient) -> None:
    r = client.get("/alerts/by-region", params={"from": "2026-04-01", "to": "2026-05-01"})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    if body:
        row = body[0]
        assert {"region_id", "region_name", "dates"} <= row.keys()
        # generate_series gives one entry per day in the window (inclusive: 31 days for April-May).
        assert len(row["dates"]) == 31


@REQUIRES_DB
def test_alerts_stats_shape(client: TestClient) -> None:
    r = client.get("/alerts/stats", params={"from": "2026-04-01", "to": "2026-05-01"})
    assert r.status_code == 200
    body = r.json()
    assert {"total", "high_confidence", "by_source"} <= body.keys()
    assert isinstance(body["by_source"], dict)
