"""R3.5 — conclusion + CV fitness tier."""

from __future__ import annotations

from app.recommendation.conclusion import build_recommendation_conclusion
from app.recommendation.cv_fitness import lookup_cv_fitness
from app.recommendation.satisfaction import GradeLookupResult


def test_cv_fitness_unsuitable():
    tier = lookup_cv_fitness(83.0)
    assert tier.tier == "unsuitable"
    assert tier.label_ko == "예측 부적합"
    assert tier.tone == "negative"


def test_cv_fitness_excellent():
    tier = lookup_cv_fitness(12.0)
    assert tier.tier == "excellent"


def test_conclusion_no_predictive_when_high_cv_and_twin_worse():
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
        grade=grade,
        scope_n_tx=286,
        selection_n=168,
        fit_n=168,
        has_twins=True,
        twin_recommended=False,
        stage2=stage2,
    )
    assert c.verdict == "no_predictive_model"
    assert c.adopt_mode == "review_only"
    assert len(c.recommended_actions) >= 3
    assert any(a.kind == "dont" for a in c.recommended_actions)
    assert any(a.action_id == "use_land_matrix" for a in c.recommended_actions)
    assert c.final_verdict_ko == "예측 부적합"
    assert c.final_verdict_emoji == "🔴"


def test_twin_recommended_when_not_run():
    grade = GradeLookupResult(grade="fair", stars=3, label_ko="보통", proceed_twin=True)
    c = build_recommendation_conclusion(
        cv_mape=45.0,
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
    assert any("Twin" in b.text for b in c.bullets)
