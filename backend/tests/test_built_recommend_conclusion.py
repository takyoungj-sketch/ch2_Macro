"""R3.5 — conclusion + 4축 해석 강도 (D-068)."""

from __future__ import annotations

from app.recommendation.conclusion import build_recommendation_conclusion
from app.recommendation.cv_fitness import (
    build_macro_diagnosis,
    lookup_cv_fitness,
    offer_structure_twin,
)
from app.recommendation.satisfaction import GradeLookupResult, lookup_predictive_fit


def test_cv_intensity_low():
    tier = lookup_cv_fitness(12.0)
    assert tier.tier == "low"
    assert tier.label_ko == "낮음"
    assert tier.tone == "accent"


def test_cv_intensity_moderate():
    tier = lookup_cv_fitness(37.5)
    assert tier.tier == "moderate"
    assert tier.label_ko == "보통"
    assert tier.tone == "accent"


def test_cv_intensity_elevated_geumjeong():
    tier = lookup_cv_fitness(58.4)
    assert tier.tier == "elevated"
    assert tier.label_ko == "높은 편"


def test_cv_intensity_high():
    tier = lookup_cv_fitness(83.0)
    assert tier.tier == "high"
    assert tier.label_ko == "높음"
    assert tier.tone == "high"


def test_predictive_fit_same_table_no_pass_fail():
    p = lookup_predictive_fit(cv_mape=58.4, asset_slice="commercial")
    assert p.label_ko == "높은 편"
    assert p.tier != "unfit"
    factory = lookup_predictive_fit(cv_mape=58.4, asset_slice="factory")
    assert factory.label_ko == p.label_ko


def test_offer_twin_by_gap_not_by_fail():
    assert offer_structure_twin(
        has_twins=True,
        cv_mape=58.4,
        mape=45.2,
        selection_n=824,
        scope_n_tx=1000,
        fit_n=824,
        min_local_n=15,
        min_fit_n=10,
    )
    assert not offer_structure_twin(
        has_twins=True,
        cv_mape=58.4,
        mape=55.0,
        selection_n=824,
        scope_n_tx=1000,
        fit_n=824,
        min_local_n=15,
        min_fit_n=10,
    )


def test_small_n_moderate_cv_is_usable_not_stable():
    d = build_macro_diagnosis(
        cv_mape=37.5,
        mape=41.5,
        adj_r_squared=0.508,
        fit_n=69,
        scope_n_tx=87,
        selection_n=69,
    )
    assert d.error.label_ko == "보통"
    assert d.sample.label_ko == "표본 주의"
    assert d.stability.label_ko == "양호"
    assert d.composite.label_ko == "활용 가능"
    assert "69건" in d.summary_ko


def test_large_n_elevated_cv_is_careful():
    d = build_macro_diagnosis(
        cv_mape=58.4,
        mape=50.0,
        adj_r_squared=0.658,
        fit_n=824,
        scope_n_tx=900,
        selection_n=824,
    )
    assert d.error.label_ko == "높은 편"
    assert d.sample.label_ko == "표본 충분"
    assert d.composite.label_ko == "신중 활용"
    assert "부적합" not in d.summary_ko


def test_large_n_high_cv_is_exploratory():
    d = build_macro_diagnosis(
        cv_mape=65.0,
        mape=55.0,
        adj_r_squared=0.66,
        fit_n=824,
        scope_n_tx=900,
        selection_n=824,
    )
    assert d.composite.label_ko == "탐색적 활용"


def test_tiny_n_is_analysis_limit():
    d = build_macro_diagnosis(
        cv_mape=30.0,
        mape=28.0,
        adj_r_squared=0.5,
        fit_n=20,
        scope_n_tx=80,
        selection_n=20,
    )
    assert d.composite.label_ko == "분석 한계"
    assert d.sample.tone == "fail"


def test_conclusion_high_cv_is_intensity_not_fail():
    grade = GradeLookupResult(grade="poor", stars=2, label_ko="미흡", proceed_twin=True)
    from app.built.schemas import RecommendationPoolCandidate, RecommendationStage2

    stage2 = RecommendationStage2(
        ran=True,
        pools=[
            RecommendationPoolCandidate(
                candidate_id="twin1",
                label="Twin top1",
                n=200,
                cv_mape=93.0,
            )
        ],
        local_cv_mape=83.0,
        fixed_blocks=["land_area"],
        fixed_response_scale="log",
    )
    c = build_recommendation_conclusion(
        cv_mape=83.0,
        mape=66.0,
        adj_r_squared=0.4,
        grade=grade,
        scope_n_tx=286,
        selection_n=168,
        fit_n=168,
        has_twins=True,
        twin_recommended=False,
        stage2=stage2,
    )
    assert c.verdict == "caution"
    assert c.adopt_mode == "review_only"
    assert c.final_verdict_ko == "높음"
    assert c.macro_diagnosis is not None
    assert c.macro_diagnosis.composite.label_ko == "탐색적 활용"
    assert "부적합" not in c.final_verdict_ko
    assert "AVM" not in c.summary_ko or "탐색" in c.summary_ko
    assert any(a.action_id == "no_avm_read" for a in c.recommended_actions)


def test_twin_recommended_when_not_run():
    grade = GradeLookupResult(grade="fair", stars=3, label_ko="보통", proceed_twin=True)
    c = build_recommendation_conclusion(
        cv_mape=45.0,
        mape=30.0,
        adj_r_squared=0.5,
        grade=grade,
        scope_n_tx=100,
        selection_n=80,
        fit_n=75,
        has_twins=True,
        twin_recommended=True,
        stage2=None,
    )
    assert c.twin_recommended is True
    assert c.twin_ran is False
    assert any("추가 검증" in b.text or "닮은" in b.text for b in c.bullets)


def test_offer_twin_even_without_neighbors_when_cv_high():
    assert offer_structure_twin(
        has_twins=False,
        cv_mape=72.1,
        mape=40.0,
        selection_n=101,
        scope_n_tx=106,
        fit_n=101,
        min_local_n=15,
        min_fit_n=10,
        admin_level="eupmyeondong",
    )


def test_offer_twin_not_when_cv_low_and_n_ok():
    assert not offer_structure_twin(
        has_twins=True,
        cv_mape=30.0,
        mape=28.0,
        selection_n=80,
        scope_n_tx=90,
        fit_n=80,
        min_local_n=15,
        min_fit_n=10,
        admin_level="eupmyeondong",
    )


def test_offer_twin_not_at_sigungu():
    assert not offer_structure_twin(
        has_twins=True,
        cv_mape=72.1,
        mape=40.0,
        selection_n=101,
        scope_n_tx=200,
        fit_n=80,
        min_local_n=15,
        min_fit_n=10,
        admin_level="sigungu",
    )


def test_twin_bullet_without_neighbors():
    grade = GradeLookupResult(grade="fair", stars=3, label_ko="보통", proceed_twin=True)
    c = build_recommendation_conclusion(
        cv_mape=72.1,
        mape=40.0,
        adj_r_squared=0.5,
        grade=grade,
        scope_n_tx=106,
        selection_n=101,
        fit_n=101,
        has_twins=False,
        twin_recommended=True,
        stage2=None,
    )
    assert c.twin_recommended is True
    assert any("추가 검증" in b.text or "닮은" in b.text for b in c.bullets)
