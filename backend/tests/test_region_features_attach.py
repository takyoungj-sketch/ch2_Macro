"""지역 프로필 공변량 join — 행 단위 지역코드 사용."""

from __future__ import annotations

import pandas as pd

from app.built.regression.region_features import (
    _scalar_from_features,
    attach_region_features,
    is_region_block,
    region_blocks_for_asset,
)


def test_region_blocks_for_commercial_includes_comm():
    blocks = region_blocks_for_asset("commercial")
    assert "region_land_p50" in blocks
    assert "region_comm_p50" in blocks
    assert "region_population" in blocks
    assert all(is_region_block(b) for b in blocks)


def test_region_blocks_price_tier_excludes_activity():
    price = region_blocks_for_asset("commercial", tier="price")
    assert price == ["region_land_p50", "region_apt_p50", "region_comm_p50"]
    assert "region_population" not in price
    assert "region_comm_n" not in price
    full = region_blocks_for_asset("commercial", tier="full")
    assert "region_population" in full
    assert "region_land_p50" in full


def test_land_p50_falls_back_to_top1_mean():
    """정규 land_*_median이 없으면 land_top1_mean_manwon_per_sqm을 쓴다."""
    from app.built.regression.region_features import _scalar_from_features, REGION_FEATURE_SPECS

    land_spec = next(s for s in REGION_FEATURE_SPECS if s.block_id == "region_land_p50")
    assert _scalar_from_features({"land_commercial_median": 120.0}, land_spec.profile_keys) == 120.0
    assert (
        _scalar_from_features({"land_top1_mean_manwon_per_sqm": 91.3}, land_spec.profile_keys)
        == 91.3
    )
    assert _scalar_from_features({"apartment_median": 200.0}, land_spec.profile_keys) is None


def test_scalar_from_features_priority():
    feats = {"land_residential_median": 100.0, "land_commercial_median": 180.0}
    assert (
        _scalar_from_features(
            feats,
            ("land_commercial_median", "land_residential_median"),
        )
        == 180.0
    )


def test_attach_uses_each_row_region_not_first_only(monkeypatch):
    df = pd.DataFrame(
        {
            "price": [1.0, 2.0, 3.0],
            "eupmyeondong_code": ["43113113", "43730250", "43113113"],
            "gross_area": [10.0, 20.0, 30.0],
        }
    )
    fake_map = {
        "43113113": {
            "region_population": 10000.0,
            "region_land_p50": 180.0,
            "region_apt_p50": 200.0,
            "region_apt_n": 50.0,
            "region_comm_p50": 150.0,
            "region_comm_n": 40.0,
        },
        "43730250": {
            "region_population": 3000.0,
            "region_land_p50": 80.0,
            "region_apt_p50": 90.0,
            "region_apt_n": 10.0,
            "region_comm_p50": 70.0,
            "region_comm_n": 5.0,
        },
    }

    monkeypatch.setattr(
        "app.built.regression.region_features.fetch_region_feature_map",
        lambda codes, **kwargs: {c: fake_map[c] for c in codes if c in fake_map},
    )

    out = attach_region_features(
        df,
        profile_version="v2.1-national",
        window_years=3,
        block_ids=["region_population", "region_land_p50"],
    )
    assert out.loc[0, "region_population"] == 10000.0
    assert out.loc[1, "region_population"] == 3000.0
    assert out.loc[2, "region_population"] == 10000.0
    assert out.loc[0, "region_land_p50"] == 180.0
    assert out.loc[1, "region_land_p50"] == 80.0
    # 원본 미변경
    assert "region_population" not in df.columns
