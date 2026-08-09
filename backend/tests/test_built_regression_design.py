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


def test_partial_regression_plots_match_ols_beta():
    rows = []
    for i in range(20):
        gross = 50 + i * 10
        land = 30 + i * 8
        age = 5 + (i % 5)
        rows.append(
            {
                "price": 500 + gross * 2 + land * 3 - age * 10,
                "gross_area": gross,
                "land_area": land,
                "building_age": age,
                "road_width_label": "8m",
                "zone_type": "일반",
                "building_use": "근린",
                "asset_type": "commercial",
            }
        )
    df = pd.DataFrame(rows)
    spec = RegressionVariableSpec(
        gross_area=True,
        land_area=True,
        building_age=True,
        road_width_dummy=False,
        zone_type_dummy=False,
        building_use_dummy=False,
    )
    from app.built.regression.engine import _fit_ols, _partial_regression_plots

    fit = _fit_ols(df, spec, "sigungu", "test", response_scale="linear")
    partials = _partial_regression_plots(df, spec, response_scale="linear")
    assert len(partials) == 3
    land_partial = next(p for p in partials if p.variable == "land_area")
    land_coef = next(c for c in fit.coefficients if c.name == "land_area")
    assert land_partial.beta is not None
    assert land_coef.estimate is not None
    assert abs(land_partial.beta - land_coef.estimate) < 1e-6
    assert land_partial.p_value == land_coef.p_value
    assert land_partial.partial_r_squared is not None
    assert 0 <= land_partial.partial_r_squared <= 1
    assert len(land_partial.points) >= 1


def test_compare_mode_gu_only_when_gu_selected_no_leaf():
    from app.built.regression.engine import _compare_mode, _filter_gu, _has_gu_selection
    from app.built.schemas import RegressionRunRequest

    req = RegressionRunRequest(
        addr1="충청북도",
        addr2="청주시",
        addr3_list=["흥덕구"],
        exclude_outliers_iqr=False,
    )
    assert _has_gu_selection(req, True) is True
    assert _compare_mode(req, True) == "gu_only"

    req_flat = RegressionRunRequest(
        addr1="충청북도",
        addr2="음성군",
        addr3_list=["금왕읍"],
        exclude_outliers_iqr=False,
    )
    assert _compare_mode(req_flat, False) == "two_way"

    df = pd.DataFrame(
        {
            "price": [100, 200, 300, 400],
            "addr3": ["흥덕구", "흥덕구", "상당구", "상당구"],
            "addr4": ["가경동", "복대동", "용암동", "금천동"],
        }
    )
    scoped = _filter_gu(df, req)
    assert len(scoped) == 2
    assert set(scoped["addr3"]) == {"흥덕구"}


def test_compare_mode_two_way_when_leaf_selected():
    from app.built.regression.engine import _compare_mode
    from app.built.schemas import RegressionRunRequest

    req = RegressionRunRequest(
        addr1="충청북도",
        addr2="청주시",
        addr3_list=["흥덕구"],
        addr4_list=["가경동"],
        exclude_outliers_iqr=False,
    )
    assert _compare_mode(req, True) == "two_way"


def test_focus_admin_level_deepest_selection():
    from app.built.regression.engine import (
        _focus_admin_level,
        _upper_admin_levels,
        _eup_scope_for_level,
    )
    from app.built.schemas import RegressionRunRequest, RiPick

    req_sig = RegressionRunRequest(
        addr1="충청북도",
        addr2="청주시",
        exclude_outliers_iqr=False,
    )
    assert _focus_admin_level(req_sig, True) == "sigungu"
    assert _upper_admin_levels("sigungu", True) == []

    req_gu = RegressionRunRequest(
        addr1="충청북도",
        addr2="청주시",
        addr3_list=["흥덕구"],
        exclude_outliers_iqr=False,
    )
    assert _focus_admin_level(req_gu, True) == "gu"
    assert _upper_admin_levels("gu", True) == ["sigungu"]

    req_leaf = RegressionRunRequest(
        addr1="충청북도",
        addr2="청주시",
        addr3_list=["흥덕구"],
        addr4_list=["가경동"],
        exclude_outliers_iqr=False,
    )
    assert _focus_admin_level(req_leaf, True) == "eupmyeondong"
    assert _upper_admin_levels("eupmyeondong", True) == ["gu", "sigungu"]

    req_ri = RegressionRunRequest(
        addr1="충청북도",
        addr2="청주시",
        addr3_list=["청원구"],
        addr4_list=["내수읍"],
        ri_list=[RiPick(eup="내수읍", ri="신대리")],
        exclude_outliers_iqr=False,
    )
    assert _focus_admin_level(req_ri, True) == "beopjungri"
    assert _upper_admin_levels("beopjungri", True) == ["eupmyeondong", "gu", "sigungu"]
    assert _eup_scope_for_level("eupmyeondong", "beopjungri", req_ri) == "parent"
    assert _eup_scope_for_level("eupmyeondong", "eupmyeondong", req_leaf) == "leaf"


def test_format_equation_includes_intercept_and_terms():
    from app.built.regression.engine import _format_equation
    from app.built.schemas import RegressionCoeff

    coefs = [
        RegressionCoeff(name="const", estimate=1000.0, std_err=100, t_value=10, p_value=0.001),
        RegressionCoeff(name="gross_area", estimate=182.5, std_err=20, t_value=9, p_value=0.001),
        RegressionCoeff(
            name="land_area", estimate=50.0, std_err=30, t_value=1.5, p_value=0.15
        ),
    ]
    eq = _format_equation(coefs, response_scale="linear")
    assert eq.startswith("금액 = 1,000")
    assert "연면적" in eq
    assert "대지면적" not in eq  # p=0.15 — 회귀식 기본(p<0.1)에서 제외


def test_correlations_empty_df_no_columns():
    from app.built.regression.engine import _correlations

    assert _correlations(pd.DataFrame([]), RegressionVariableSpec()) == []


def test_flat_sido_addr2_row_match():
    from app.built.regression.engine import _addr2_row_match, _filter_by_region_units
    from app.built.schemas import RegressionRunRequest

    df = pd.DataFrame(
        {
            "addr1": ["세종특별자치시", "세종특별자치시"],
            "addr2": [None, ""],
            "addr3": ["조치원읍", "연서면"],
            "addr4": ["", ""],
            "addr5": ["", ""],
            "eupmyeondong_code": ["36110250", "36110360"],
            "price": [100, 200],
        }
    )
    mask = _addr2_row_match(df, "__FLAT_SIDO__")
    assert mask.all()
    req = RegressionRunRequest(
        addr1="세종특별자치시",
        addr2="__FLAT_SIDO__",
        region_addrs=["세종특별자치시|연서면|연서면"],
        region_codes=["36110360"],
        region_code_level="eupmyeondong",
    )
    out = _filter_by_region_units(df, req)
    assert len(out) == 1
    assert out.iloc[0]["addr3"] == "연서면"
