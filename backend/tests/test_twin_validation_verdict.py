"""Twin Validation verdict (Local vs Twin CV-MAPE)."""

from __future__ import annotations

from app.built.schemas import RecommendationPoolCandidate
from app.recommendation.twin_validation import (
    TWIN_VALIDATION_EPSILON_PP,
    build_twin_validation_verdict,
)


def _pool(cid: str, cv: float, n: int = 100) -> RecommendationPoolCandidate:
    return RecommendationPoolCandidate(
        candidate_id=cid,
        label=cid,
        n=n,
        cv_mape=cv,
        cv_mape_delta=None,
    )


def test_verdict_improved_when_delta_ge_epsilon():
    primary = _pool("twin_pool_n1", 67.16)
    v = build_twin_validation_verdict(
        ran=True,
        skipped_reason=None,
        local_cv_mape=88.63,
        decision="twin_pool_n1",
        primary=primary,
        pools=[primary, _pool("twin_pool_n3", 125.0)],
    )
    assert v.verdict == "improved"
    assert v.twin_adopt_recommended is True
    assert v.cv_mape_delta == 21.47
    assert v.epsilon_pp == TWIN_VALIDATION_EPSILON_PP


def test_verdict_worse_keeps_local_when_decision_local():
    pools = [_pool("twin_pool_n1", 67.16), _pool("twin_pool_n3", 63.42)]
    v = build_twin_validation_verdict(
        ran=True,
        skipped_reason=None,
        local_cv_mape=59.46,
        decision="local",
        primary=None,
        pools=pools,
    )
    assert v.verdict == "worse"
    assert v.twin_adopt_recommended is False
    assert v.compared_candidate_id == "twin_pool_n3"
    assert v.cv_mape_delta == -3.96


def test_verdict_tie_within_epsilon():
    primary = _pool("twin_pool_n1", 30.2)
    v = build_twin_validation_verdict(
        ran=True,
        skipped_reason=None,
        local_cv_mape=30.0,
        decision="twin_pool_n1",
        primary=primary,
        pools=[primary],
        epsilon_pp=0.5,
    )
    assert v.verdict == "tie"
    assert v.twin_adopt_recommended is False


def test_verdict_skipped_when_not_ran():
    v = build_twin_validation_verdict(
        ran=False,
        skipped_reason="Profile Twin 후보가 전달되지 않았습니다.",
        local_cv_mape=40.0,
        decision="local",
        primary=None,
        pools=[],
    )
    assert v.verdict == "skipped"
    assert v.twin_adopt_recommended is False
    assert "전달되지" in v.summary_ko
