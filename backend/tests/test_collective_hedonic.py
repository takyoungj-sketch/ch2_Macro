"""집합 2단계 헤도닉 — 단위 테스트."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.collective.hedonic.enrichment import _UQA_RE, resolve_uqa_for_buildings
from app.collective.hedonic.stage1 import apply_iqr_filter, build_stage1_from_transactions
from app.collective.hedonic.stage2 import run_attribute_effects, vintage_bin


def test_zone_filter_keeps_management_and_farmland():
    """관리(UQB)·농림(UQC)·자연환경보전(UQD)도 용도지역이다 — UQA만 보면 통째로 빠진다."""
    for code in ("UQA122", "UQA430", "UQB100", "UQB300", "UQC001", "UQD001"):
        assert _UQA_RE.match(code), code
    # 용도지구·구역·시설은 용도지역이 아니다
    for code in ("UQQ902", "UQS121", "UQT310", "UQM110", "UQW100", "UDV100"):
        assert not _UQA_RE.match(code), code


def test_resolve_uqa_demotes_urban_broad_label():
    """같은 필지에 '도시지역'(UQA001)과 세부가 함께 있으면 세부를 골라야 한다."""
    buildings = pd.DataFrame(
        {"building_key": ["b1", "b2"], "beopjungri_code": ["4311310100"] * 2, "lot_number": ["100", "200"]}
    )
    ald = pd.DataFrame(
        {
            "beopjungri_code": ["4311310100"] * 3,
            "lot_number": ["100", "100", "200"],
            "uqa_code": ["UQA001", "UQA122", "UQA001"],
            "uqa_label": ["도시지역", "제2종일반주거지역", "도시지역"],
        }
    )
    out = resolve_uqa_for_buildings(buildings, ald).set_index("building_key")
    assert out.loc["b1", "uqa_code"] == "UQA122"
    assert out.loc["b1", "zone_resolution"] == "exact"
    assert out.loc["b2", "zone_resolution"] == "coarse_only"


def test_vintage_bin_labels():
    assert vintage_bin(1985) == "~1989"
    assert vintage_bin(1995) == "1990-1999"
    assert vintage_bin(2005) == "2000-2009"
    assert vintage_bin(2015) == "2010-2019"
    assert vintage_bin(2022) == "2020+"


def test_iqr_filter_drops_extremes():
    df = pd.DataFrame({"unit_price": [100, 110, 105, 108, 1000]})
    out = apply_iqr_filter(df)
    assert len(out) == 4
    assert out["unit_price"].max() < 200


def test_stage1_quality_index_centered_per_sigungu():
    """시군구 내 quality_index 평균 ≈ 0."""
    rng = np.random.default_rng(0)
    rows = []
    for bk_i in range(25):
        bk = f"b{bk_i:02d}"
        base = 800 + bk_i * 20
        for _ in range(15):
            rows.append(
                {
                    "building_key": bk,
                    "sigungu_code": "30110",
                    "unit_price": base + rng.normal(0, 5),
                    "exclusive_area": 80 + rng.normal(0, 3),
                    "floor": float(rng.integers(2, 15)),
                    "contract_year": 2022,
                    "contract_date": "2022-06-01",
                }
            )
    tx = pd.DataFrame(rows)
    result = build_stage1_from_transactions(
        tx,
        as_of_month=pd.Timestamp("2026-07-01").date(),
        window_years=5,
    )
    assert result.included_sigungu >= 1
    assert result.building_rows
    qi = [r["quality_index"] for r in result.building_rows]
    assert abs(float(np.mean(qi))) < 1e-6


def test_stage2_spec_a_returns_coefficients():
    df = pd.DataFrame(
        {
            "building_key": [f"k{i}" for i in range(40)],
            "sigungu_code": ["30110"] * 40,
            "sido_code": ["30"] * 40,
            "quality_index": np.linspace(-0.1, 0.1, 40),
            "quality_se": [0.05] * 40,
            "match_tier": ["A"] * 40,
            "brand": ["브랜드A"] * 20 + [None] * 20,
            "builder_group": ["시공A"] * 40,
            "structure_group": ["RC"] * 40,
            "households": np.linspace(300, 1200, 40),
            "max_floor": [15] * 40,
            "parking_per_household": [1.2] * 40,
            "approved_year": [2005] * 40,
            "building_year": [2005] * 40,
            "danji_class": ["아파트"] * 40,
            "supply_type": ["분양"] * 40,
            "danji_code": [f"d{i}" for i in range(40)],
            "attr_quality_flags": [None] * 40,
            "n_tx": [50] * 40,
        }
    )
    res = run_attribute_effects(
        df,
        spec="A",
        include_terms={"brand", "scale", "structure", "vintage"},
        min_buildings_per_term=10,
        bootstrap_reps=0,
    )
    assert res.n_buildings >= 30
    assert res.equation
    assert any(c["term_kind"] == "brand" for c in res.coefficients)
