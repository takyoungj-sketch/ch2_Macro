"""Tests for Profile-native Twin vector projection & similarity (D-029 Phase B)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))

from profile_twin import compute_similarity, load_twin_catalog, project_profile  # noqa: E402


def _sample_features(*, apt_count: int = 87, apt_median: float = 256.0) -> dict:
    return {
        "population": 12000,
        "dominant_type": "아파트",
        "market_presence": {"아파트": 1, "토지": 1},
        "apartment_count": apt_count,
        "apartment_p25": 200.0,
        "apartment_median": apt_median,
        "apartment_p75": 320.0,
        "yearly_mix": {
            "count_share_by_type": {
                "토지": 0.1,
                "상가": 0.05,
                "공장": 0.02,
                "단독다가구": 0.03,
                "아파트": 0.6,
                "오피스텔": 0.05,
                "연립다세대": 0.1,
                "분양권": 0.05,
            }
        },
        "land_top1": {
            "zone": "주거",
            "jimok": "대",
            "jimok_code": "dev",
            "count": 50,
            "mean_manwon_per_sqm": 800.0,
        },
        "land_top2": {
            "zone": "녹지",
            "jimok": "임",
            "jimok_code": "forest",
            "count": 30,
            "mean_manwon_per_sqm": 120.0,
        },
    }


def test_apt_mask_requires_count_15():
    cat = load_twin_catalog()
    low = project_profile(
        _sample_features(apt_count=10),
        region_level="beopjungri",
        region_code="4373025034",
        catalog=cat,
    )
    assert low.mask("apt_p50") == 0.0
    assert low.values.get("apt_p50") is None

    ok = project_profile(
        _sample_features(apt_count=87),
        region_level="beopjungri",
        region_code="4373025034",
        catalog=cat,
    )
    assert ok.mask("apt_p50") == 1.0
    assert ok.values.get("apt_p50") == 256.0


def test_similarity_identical_profiles_high():
    cat = load_twin_catalog()
    feats = _sample_features()
    a = project_profile(feats, region_level="eupmyeondong", region_code="4311313800", catalog=cat)
    b = project_profile(feats, region_level="eupmyeondong", region_code="4311313900", catalog=cat)
    result = compute_similarity(a, b, catalog=cat)
    assert result.similarity >= 0.95
    assert "market_mix" in result.score_detail
    assert result.score_detail["represent_market"].score > 0


def test_similarity_different_dominant_market_lower():
    cat = load_twin_catalog()
    a_feats = _sample_features()
    b_feats = _sample_features()
    b_feats["dominant_type"] = "토지"
    a = project_profile(a_feats, region_level="eupmyeondong", region_code="A", catalog=cat)
    b = project_profile(b_feats, region_level="eupmyeondong", region_code="B", catalog=cat)
    same = compute_similarity(a, a, catalog=cat)
    diff = compute_similarity(a, b, catalog=cat)
    assert diff.similarity < same.similarity


def test_factory_profile_weight_uses_factory_p50_block():
    from profile_twin.weight import load_twin_weights

    cat = load_twin_catalog()
    feats = _sample_features()
    feats["market_presence"] = {"공장": 1, "토지": 1}
    feats["factory_count"] = 20
    feats["factory_median"] = 180.0
    feats["dominant_type"] = "공장"
    a = project_profile(feats, region_level="eupmyeondong", region_code="A", catalog=cat)
    assert a.mask("factory_p50") == 1.0
    w = load_twin_weights(twin_profile="built_factory")
    result = compute_similarity(a, a, catalog=cat, weights=w)
    assert "factory_profile" in result.block_scores
    assert result.block_scores["factory_profile"] > 0.9
