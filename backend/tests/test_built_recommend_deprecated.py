"""R3 — deprecated suggest/compare headers."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_suggest_compare_deprecation_headers():
    client = TestClient(app)
    body = {
        "asset_type": "commercial",
        "variables": {
            "gross_area": True,
            "land_area": False,
            "building_age": False,
            "road_width_dummy": False,
            "road_code": False,
            "zone_type_dummy": False,
            "building_use_dummy": False,
            "asset_type_dummy": False,
            "region_leaf_dummy": False,
        },
        "exclude_outliers_iqr": False,
    }
    for path in ("/api/built/regression/suggest", "/api/built/regression/compare"):
        r = client.post(path, json=body)
        assert r.status_code in {200, 400, 422, 500}
        if r.status_code == 200:
            assert r.headers.get("deprecation") == "true"
            assert "regression/recommend" in (r.headers.get("link") or "")
            payload = r.json()
            assert payload.get("deprecated") is True
            assert payload.get("successor_path") == "/built/regression/recommend"
