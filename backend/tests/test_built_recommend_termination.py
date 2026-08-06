"""R2 — termination builder."""

from __future__ import annotations

from app.built.schemas import ModelCandidate, ModelMetrics, RegressionVariableSpec, RecommendationStage2
from app.recommendation.satisfaction import GradeLookupResult
from app.recommendation.termination import build_termination_r2


def _primary(cv: float | None = 30.0) -> ModelCandidate:
    return ModelCandidate(
        rank=1,
        blocks=["land_area"],
        variables=RegressionVariableSpec(land_area=True),
        response_scale="log",
        metrics=ModelMetrics(model_type="log", cv_mape=cv),
    )


def test_good_grade_skips_twin_when_no_stage2():
    grade = GradeLookupResult(grade="good", stars=4, label_ko="양호", proceed_twin=False)
    term = build_termination_r2(
        grade=grade,
        selection_n=40,
        scope_n_tx=50,
        primary=_primary(25),
        alternate=None,
        truncated=False,
        stage2=None,
    )
    assert term.stage_reached == 1
    assert term.action == "stop"
    assert term.grade == "good"


def test_fair_with_stage2_ran():
    grade = GradeLookupResult(grade="fair", stars=3, label_ko="보통", proceed_twin=True)
    stage2 = RecommendationStage2(
        ran=True,
        pools=[],
        decision="twin_pool_n1",
        decision_reason="CV-MAPE improved",
        fixed_blocks=["land_area"],
        fixed_response_scale="log",
    )
    term = build_termination_r2(
        grade=grade,
        selection_n=20,
        scope_n_tx=25,
        primary=_primary(40),
        alternate=None,
        truncated=False,
        stage2=stage2,
    )
    assert term.stage_reached == 2
    assert any("2단계" in r for r in term.reasons)
