"""회귀 설계행렬 — road_width·통합 유형."""

from __future__ import annotations

import pandas as pd

from app.built.regression.engine import _build_design_matrix
from app.built.schemas import RegressionVariableSpec


def test_road_width_dummy():
    df = pd.DataFrame(
        {
            "price": [100, 200, 300],
            "gross_area": [10, 20, 30],
            "land_area": [5, 5, 5],
            "building_age": [1, 2, 3],
            "road_width_label": ["8m", "8m", "12m"],
            "zone_type": ["일반", "일반", "일반"],
            "building_use": ["근린", "근린", "근린"],
            "asset_type": ["commercial", "commercial", "commercial"],
        }
    )
    spec = RegressionVariableSpec(
        gross_area=False,
        land_area=False,
        building_age=False,
        road_width_dummy=True,
        zone_type_dummy=False,
        building_use_dummy=False,
    )
    y, X, meta = _build_design_matrix(df, spec)
    assert len(y) == 3
    assert meta is not None
    assert any(c.startswith("road_") for c in meta.feature_columns)


def test_unified_asset_type_dummy():
    df = pd.DataFrame(
        {
            "price": [100, 200, 300, 400],
            "gross_area": [10, 20, 30, 40],
            "land_area": [5, 5, 5, 5],
            "building_age": [1, 2, 3, 4],
            "road_width_label": ["8m", "8m", "8m", "8m"],
            "zone_type": ["일반", "일반", None, "일반"],
            "building_use": ["근린", "근린", "단독", "근린"],
            "asset_type": ["commercial", "factory", "detached", "commercial"],
        }
    )
    spec = RegressionVariableSpec(
        gross_area=True,
        land_area=False,
        building_age=False,
        road_width_dummy=False,
        zone_type_dummy=True,
        building_use_dummy=False,
        asset_type_dummy=True,
    )
    y, X, meta = _build_design_matrix(df, spec, unified=True)
    assert len(y) == 4
    assert meta is not None
    assert any(c.startswith("atype_") for c in meta.feature_columns)


def test_region_leaf_dummy():
    df = pd.DataFrame(
        {
            "price": [100, 200, 300, 400, 500, 600],
            "gross_area": [10, 20, 30, 40, 50, 60],
            "land_area": [5, 5, 5, 5, 5, 5],
            "building_age": [1, 2, 3, 4, 5, 6],
            "road_width_label": ["8m"] * 6,
            "zone_type": ["일반"] * 6,
            "building_use": ["근린"] * 6,
            "asset_type": ["commercial"] * 6,
            "addr3": ["동A", "동A", "동B", "동B", "동C", "동C"],
        }
    )
    spec = RegressionVariableSpec(
        gross_area=True,
        land_area=False,
        building_age=False,
        road_width_dummy=False,
        zone_type_dummy=False,
        building_use_dummy=False,
        region_leaf_dummy=True,
    )
    y, X, meta = _build_design_matrix(df, spec, region_col="addr3")
    assert len(y) == 6
    assert meta is not None
    assert meta.region_leaves == ["동A", "동B", "동C"]
    assert meta.region_reference == "동A"
    assert any(c.startswith("loc_") for c in meta.feature_columns)
    assert "loc_동B" in meta.feature_columns
    assert "loc_동C" in meta.feature_columns
    assert "loc_동A" not in meta.feature_columns


def test_region_dummy_skipped_at_sigungu():
    rows = []
    for i in range(12):
        dong = ["동A", "동B", "동C"][i % 3]
        rows.append(
            {
                "price": 100 + i * 50,
                "gross_area": 10 + i * 5,
                "land_area": 5,
                "building_age": 1 + i,
                "road_width_label": "8m",
                "zone_type": "일반",
                "building_use": "근린",
                "asset_type": "commercial",
                "addr3": dong,
            }
        )
    df = pd.DataFrame(rows)
    spec = RegressionVariableSpec(
        gross_area=True,
        land_area=False,
        building_age=False,
        road_width_dummy=False,
        zone_type_dummy=False,
        building_use_dummy=False,
        region_leaf_dummy=True,
    )
    from app.built.regression.engine import _fit_ols

    sig = _fit_ols(df, spec, "sigungu", "test")
    assert not any(c.name.startswith("loc_") for c in sig.coefficients)

    eup = _fit_ols(df, spec, "eupmyeondong", "test")
    assert any(c.name.startswith("loc_") for c in eup.coefficients)


def test_fit_ols_reports_mape():
    rows = []
    for i in range(12):
        price = 1000 + i * 50
        rows.append(
            {
                "price": price,
                "gross_area": 100 + i * 5,
                "land_area": 50,
                "building_age": 10 + i,
                "road_width_label": "8m",
                "zone_type": "일반",
                "building_use": "근린",
                "asset_type": "commercial",
            }
        )
    df = pd.DataFrame(rows)
    spec = RegressionVariableSpec(
        gross_area=True,
        land_area=False,
        building_age=True,
        road_width_dummy=False,
        zone_type_dummy=False,
        building_use_dummy=False,
    )
    from app.built.regression.engine import _fit_ols

    result = _fit_ols(df, spec, "sigungu", "test", response_scale="linear")
    assert result.n == 12
    assert result.mape is not None
    assert 0 <= result.mape < 100
