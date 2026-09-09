"""집합 분석 게이트 — 회귀 실행 하한 15 · 권장 30 · 최근 15는 경고."""

from app.collective.analysis_gates import (
    MIN_COUNT_REGRESSION,
    MIN_COUNT_REGRESSION_RUN,
    evaluate_analysis_gates,
)


def test_regression_runnable_from_15():
    low = evaluate_analysis_gates(14, 14)
    assert low.regression_eligible is False
    assert low.floor_index_eligible is False

    mid = evaluate_analysis_gates(20, 8)
    assert mid.regression_eligible is True
    assert any("참고용" in m for m in mid.messages)
    assert any("최근 3년" in m for m in mid.messages)
    assert not any("코호트" in m for m in mid.messages)

    edge = evaluate_analysis_gates(15, 15)
    assert edge.regression_eligible is True
    assert any("참고용" in m for m in edge.messages)

    ok = evaluate_analysis_gates(40, 20)
    assert ok.regression_eligible is True
    assert not any("참고용" in m for m in ok.messages)
    assert not any("최근 3년" in m for m in ok.messages)


def test_recent_thin_is_not_a_lock():
    g = evaluate_analysis_gates(35, 4)
    assert g.regression_eligible is True
    assert any("잠금 조건이 아닙니다" in m for m in g.messages)

    plenty_recent_thin = evaluate_analysis_gates(60, 4, suggest_cohort=True)
    assert plenty_recent_thin.regression_eligible is True
    assert plenty_recent_thin.floor_index_eligible is True
    assert not any("코호트" in m for m in plenty_recent_thin.messages)


def test_cohort_hint_only_when_cannot_run_or_floor():
    g = evaluate_analysis_gates(20, 10, suggest_cohort=True)
    assert g.regression_eligible is True
    assert any("코호트" in m for m in g.messages)
    assert any("효용지수" in m for m in g.messages)

    blocked = evaluate_analysis_gates(10, 2, suggest_cohort=True)
    assert blocked.regression_eligible is False
    assert any("코호트" in m for m in blocked.messages)

    plenty = evaluate_analysis_gates(60, 20, suggest_cohort=True)
    assert plenty.floor_index_eligible is True
    assert plenty.regression_eligible is True
    assert not any("코호트" in m for m in plenty.messages)


def test_constants():
    assert MIN_COUNT_REGRESSION_RUN == 15
    assert MIN_COUNT_REGRESSION == 30
