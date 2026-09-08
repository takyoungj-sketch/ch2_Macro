"""D-066 Twin 구조 순위 · 실질적 개선 띠 · 계수 안정."""

from __future__ import annotations

from app.recommendation.twin_structure import (
    classify_search_delta,
    coeff_stability,
    decide_twin_prefix,
    practical_band_pp,
    rank_neighbors_by_structure,
    structure_score_from_detail,
)


def test_structure_score_ignores_apartment_price_block():
    detail = {
        "block_scores": {"population": 0.9, "market_mix": 0.8, "apartment_profile": 0.1},
        "features": {"land_profile": {"note": "Top3 Jaccard 0.50, 공통셀 단가 sim 0.99"}},
        "represent_market_adjustment": 0.0,
    }
    score = structure_score_from_detail(detail)
    # 0.9*0.25 + 0.8*0.55 + 0.50*0.20 = 0.225+0.44+0.10 = 0.765
    assert abs(score - 0.765) < 1e-6


def test_rank_neighbors_by_structure_orders_mix_not_similarity():
    neighbors = [
        {
            "region_code": "A",
            "similarity_score": 0.99,
            "detail_scores": {"block_scores": {"population": 0.2, "market_mix": 0.2}},
        },
        {
            "region_code": "B",
            "similarity_score": 0.50,
            "detail_scores": {"block_scores": {"population": 0.9, "market_mix": 0.9}},
        },
    ]
    ranked = rank_neighbors_by_structure(neighbors, top_k=2)
    assert ranked[0]["region_code"] == "B"
    assert ranked[0]["structure_rank"] == 1


def test_practical_band_is_tolerance_not_tiny_delta():
    band = practical_band_pp(44.5)
    assert band == max(0.5, 44.5 * 0.02)
    assert classify_search_delta(0.02, band) == "tie"
    assert classify_search_delta(1.8, band) == "improved"


def test_coeff_sign_flip_fails_stability():
    status, notes = coeff_stability({"gross_area": 155.0}, {"gross_area": -42.0})
    assert status == "fail"
    assert any("부호 반전" in n for n in notes)


def test_decide_prefix_keeps_local_when_confirm_fails():
    d = decide_twin_prefix(
        local_n=30,
        local_search_cv=44.5,
        local_confirm_cv=45.0,
        local_coeffs={"gross_area": 10.0},
        local_blocks=["gross_area"],
        prefixes=[
            {
                "candidate_id": "twin_prefix_k1",
                "label": "Local + Twin 1위",
                "prefix_k": 1,
                "region_codes": ["T1"],
                "n": 80,
                "search_cv_mape": 39.8,
                "confirm_cv_mape": 46.5,
                "key_coefficients": {"gross_area": 9.5},
                "blocks": ["gross_area"],
            }
        ],
    )
    assert d.decision == "local"
    assert d.adopt_recommended is False
    assert d.selected_step_id == "local"
    assert d.search_winner_step_id == "twin_prefix_k1"
    winner = next(s for s in d.steps if s.step_id == "twin_prefix_k1")
    local = next(s for s in d.steps if s.step_id == "local")
    assert winner.search_picked is True
    assert winner.selected is False
    assert local.selected is True


def test_decide_prefix_recommends_when_confirm_also_improves():
    d = decide_twin_prefix(
        local_n=30,
        local_search_cv=44.5,
        local_confirm_cv=45.0,
        local_coeffs={"gross_area": 10.0},
        local_blocks=["gross_area"],
        prefixes=[
            {
                "candidate_id": "twin_prefix_k1",
                "label": "Local + Twin 1위",
                "prefix_k": 1,
                "region_codes": ["T1"],
                "n": 80,
                "search_cv_mape": 39.8,
                "confirm_cv_mape": 40.0,
                "key_coefficients": {"gross_area": 9.5},
                "blocks": ["gross_area"],
            }
        ],
    )
    assert d.adopt_recommended is True
    assert d.decision == "twin_prefix_k1"
    winner = next(s for s in d.steps if s.step_id == "twin_prefix_k1")
    assert winner.search_picked is True
    assert winner.selected is True


def test_n_increase_without_practical_cv_keeps_local():
    d = decide_twin_prefix(
        local_n=30,
        local_search_cv=44.5,
        local_confirm_cv=45.0,
        local_coeffs={"gross_area": 155.0},
        local_blocks=["gross_area"],
        prefixes=[
            {
                "candidate_id": "twin_prefix_k1",
                "label": "Local + Twin 1위",
                "prefix_k": 1,
                "region_codes": ["T1"],
                "n": 150,
                "search_cv_mape": 44.4,
                "confirm_cv_mape": 40.0,
                "key_coefficients": {"gross_area": 149.0},
                "blocks": ["gross_area"],
            }
        ],
    )
    assert d.decision == "local"
    assert d.adopt_recommended is False
    assert not any(s.search_picked for s in d.steps)


def test_recommend_narrative_explains_why_twin():
    from app.ai.built_recommend_narrative import interpret_built_recommend

    result = interpret_built_recommend(
        diagnostics={
            "analysis_scope": {"scope_n_tx": 301},
            "stage1": {
                "selection_n": 147,
                "fit_n": 147,
                "satisfaction": {"cv_mape": 44.5},
                "primary": {"blocks": ["gross_area"]},
            },
            "stage2": {
                "ran": True,
                "twin_validation": {"summary_ko": "확인 CV와 계수 안정으로 Twin 채택을 권고합니다."},
                "twin_experiments": [
                    {
                        "step_id": "local",
                        "label": "Local",
                        "prefix_k": 0,
                        "n": 147,
                        "search_cv_mape": 44.5,
                        "key_coefficients": {"gross_area": 155.0},
                    },
                    {
                        "step_id": "twin_prefix_k1",
                        "label": "Local + Twin 1위",
                        "prefix_k": 1,
                        "n": 213,
                        "search_cv_mape": 41.2,
                        "search_cv_delta": 3.3,
                        "confirm_cv_mape": 41.8,
                        "search_picked": True,
                        "selected": True,
                        "stability": "ok",
                        "key_coefficients": {"gross_area": 149.0},
                        "verdict_ko": "탐색 CV 개선",
                    },
                ],
            },
            "conclusion": {"predictive_fit": {"label_ko": "주의"}, "cv_mape": 44.5},
        },
        scope_label="청주시",
        message="",
    )
    assert "213건" in result.answer
    assert "41.2%" in result.answer
    assert "연면적" in result.answer
    assert "왜 이 Twin을 붙였나요?" in result.followups
