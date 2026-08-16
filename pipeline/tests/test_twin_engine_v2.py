"""Twin Engine V2 (D-044) — 순수 점수·문·가중."""

from __future__ import annotations

import math
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))

from profile_twin.v2 import (  # noqa: E402
    compute_similarity_v2,
    expand_nhop,
    extract_snapshot,
    load_v2_weights,
    pass_population_log_gate,
)


def _feats(
    *,
    pop: float | None = 12000,
    apt_count: int = 80,
    apt_p50: float = 250.0,
    land_price: float = 800.0,
    office_share: float = 0.05,
    jimok_dev: float = 0.6,
) -> dict:
    rest = max(0.0, 1.0 - 0.6 - office_share)
    return {
        "population": pop,
        "apartment_count": apt_count,
        "apartment_p25": 200.0,
        "apartment_median": apt_p50,
        "apartment_p75": 320.0,
        "yearly_mix": {
            "count_share_by_type": {
                "토지": 0.1,
                "상가": 0.05,
                "공장": 0.02,
                "단독다가구": 0.03,
                "아파트": 0.6,
                "오피스텔": office_share,
                "연립다세대": rest * 0.7,
                "분양권": rest * 0.3,
            }
        },
        "jimok_group_composition": {
            "jimok_group_share_agri": 0.1,
            "jimok_group_share_forest": 0.1,
            "jimok_group_share_dev": jimok_dev,
            "jimok_group_share_infra": 0.1,
            "jimok_group_share_water": 0.05,
            "jimok_group_share_special": 0.03,
            "jimok_group_share_other": max(0.0, 0.62 - jimok_dev),
        },
        "land_top1": {
            "zone": "주거",
            "jimok_code": "dev",
            "count": 40,
            "mean_manwon_per_sqm": land_price,
        },
        "land_top2": {
            "zone": "녹지",
            "jimok_code": "forest",
            "count": 20,
            "mean_manwon_per_sqm": 120.0,
        },
    }


def test_v2_yaml_roles_and_internal_weights():
    w = load_v2_weights()
    assert w.version == "2.0"
    assert w.population_max_ratio == 2.0
    cmp = w.role("compare")
    pool = w.role("pool")
    assert abs(cmp.structure_weight - 0.6) < 1e-9
    assert abs(cmp.market_weight - 0.4) < 1e-9
    assert abs(pool.structure_weight - 0.4) < 1e-9
    assert abs(pool.market_weight - 0.6) < 1e-9
    assert abs(sum(w.structure.values()) - 1.0) < 1e-6
    assert abs(sum(w.market.values()) - 1.0) < 1e-6
    assert pool.n_hop == 2


def test_population_null_rejected():
    assert pass_population_log_gate(None, 1000) is False
    assert pass_population_log_gate(1000, None) is False
    assert pass_population_log_gate(0, 1000) is False


def test_population_log2_gate():
    assert pass_population_log_gate(1000, 2000) is True
    assert pass_population_log_gate(1000, 1999) is True
    assert pass_population_log_gate(1000, 2001) is False
    assert pass_population_log_gate(1000, 500) is True
    assert pass_population_log_gate(1000, 499) is False


def test_identical_profiles_high_score_and_full_confidence():
    a = extract_snapshot(_feats(), region_code="4311313800")
    b = extract_snapshot(_feats(), region_code="4311313900")
    out = compute_similarity_v2(a, b, role="compare")
    assert out.twin_score >= 0.99
    assert out.confidence >= 0.99
    assert "apt_p50" in out.used_blocks
    assert not out.dropped_blocks


def test_missing_apt_is_dropped_not_zeroed():
    a = extract_snapshot(_feats(), region_code="A")
    b_feats = _feats(apt_count=3)
    b = extract_snapshot(b_feats, region_code="B")
    assert b.apt_price_ok is False
    out = compute_similarity_v2(a, b, role="compare")
    assert "apt_p50" in out.dropped_blocks
    assert "apt_spread" in out.dropped_blocks
    assert out.confidence < 0.95
    assert out.twin_score > 0.5


def test_mix_zero_is_structure_not_a_dropped_block():
    a = extract_snapshot(_feats(office_share=0.0), region_code="A")
    b = extract_snapshot(_feats(office_share=0.4), region_code="B")
    same = compute_similarity_v2(a, a, role="compare")
    diff = compute_similarity_v2(a, b, role="compare")
    assert "market_mix" in diff.used_blocks
    mix_term = next(t for t in diff.terms if t.key == "market_mix")
    assert mix_term.used
    assert diff.twin_score < same.twin_score


def test_compare_vs_pool_weights_change_rank_emphasis():
    a = extract_snapshot(_feats(), region_code="A")
    similar_struct = extract_snapshot(_feats(apt_p50=400.0, land_price=400.0), region_code="B")
    similar_price = extract_snapshot(
        _feats(office_share=0.35, jimok_dev=0.2, apt_p50=252.0, land_price=790.0),
        region_code="C",
    )
    cmp_b = compute_similarity_v2(a, similar_struct, role="compare")
    cmp_c = compute_similarity_v2(a, similar_price, role="compare")
    pool_b = compute_similarity_v2(a, similar_struct, role="pool")
    pool_c = compute_similarity_v2(a, similar_price, role="pool")
    # 가격이 비슷한 C는 풀에서 상대적으로 더 유리해야 한다.
    cmp_gap = cmp_b.twin_score - cmp_c.twin_score
    pool_gap = pool_b.twin_score - pool_c.twin_score
    assert pool_gap < cmp_gap


def test_expand_nhop_bfs():
    adj = {"A": ["B"], "B": ["A", "C"], "C": ["B", "D"], "D": ["C"]}
    assert expand_nhop(adj, ["A"], 0) == {"A"}
    assert expand_nhop(adj, ["A"], 1) == {"A", "B"}
    assert expand_nhop(adj, ["A"], 2) == {"A", "B", "C"}
    assert math.isclose(2.0, 2.0)
