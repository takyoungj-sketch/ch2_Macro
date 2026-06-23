"""Twin v8 scoring 단위 테스트."""

from __future__ import annotations

from twin_v8.scoring import (
    RegionProfile,
    compute_pair_scores,
    jaccard_similarity,
    pass_population_ratio,
    price_ratio_similarity,
)


def test_pass_population_0_6_to_1_7():
    assert pass_population_ratio(100_000, 60_000) is True
    assert pass_population_ratio(100_000, 170_000) is True
    assert pass_population_ratio(100_000, 50_000) is False
    assert pass_population_ratio(100_000, 200_000) is False


def test_jaccard():
    assert jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"}) == 0.5


def test_price_ratio_sim_identical():
    assert abs(price_ratio_similarity(100.0, 100.0) - 1.0) < 1e-9


def test_compute_pair_scores_basic():
    cells_a = {
        "자연녹지|답": {"count": 50, "mean": 150.0},
        "계획관리|전": {"count": 40, "mean": 140.0},
        "상업|대": {"count": 10, "mean": 500.0},
    }
    cells_b = {
        "자연녹지|답": {"count": 45, "mean": 145.0},
        "계획관리|전": {"count": 38, "mean": 135.0},
        "주거|대": {"count": 20, "mean": 200.0},
    }
    anchor = RegionProfile(
        region_code="43111",
        region_level="sigungu",
        land_cells=cells_a,
        land_total_tx=100,
        population=100_000,
        collective={"p25": 3000, "median": 4000, "p75": 5000, "count": 80},
    )
    twin = RegionProfile(
        region_code="43113",
        region_level="sigungu",
        land_cells=cells_b,
        land_total_tx=103,
        population=120_000,
        collective={"p25": 2900, "median": 4100, "p75": 5200, "count": 90},
    )
    r = compute_pair_scores(anchor, twin, top_n=3)
    assert r is not None
    assert 0 <= r.twin_score <= 100
    assert 0 <= r.confidence <= 100
    assert len(r.intersection_cells) == 2
    assert "자연녹지|답" in r.intersection_cells
    assert r.land_struct_pts == 0.5 * 30  # 2/4 jaccard on top3
    assert r.explanation_ko


def test_beopjungri_uses_eup_collective():
    anchor = RegionProfile(
        region_code="4377025028",
        region_level="beopjungri",
        land_cells={"계획|전": {"count": 5, "mean": 100.0}},
        land_total_tx=5,
        population=500,
        collective={"p25": 1, "median": 2, "p75": 3, "count": 10},
        collective_source_level="eupmyeondong",
    )
    twin = RegionProfile(
        region_code="4377025033",
        region_level="beopjungri",
        land_cells={"계획|전": {"count": 4, "mean": 105.0}},
        land_total_tx=4,
        population=600,
        collective={"p25": 1, "median": 2, "p75": 3, "count": 10},
        collective_source_level="eupmyeondong",
    )
    r = compute_pair_scores(anchor, twin, top_n=3)
    assert r is not None
    assert "eupmyeondong" in (r.explanation_ko or "")
