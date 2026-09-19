"""R2 — satisfaction grade lookup."""

from __future__ import annotations

from app.recommendation.satisfaction import grade_cv_basis, lookup_built_satisfaction


def test_excellent_grade_low_cv():
    r = lookup_built_satisfaction(cv_mape=18.0, selection_n=40, asset_slice="commercial")
    assert r.grade == "excellent"
    assert r.stars == 5
    assert r.proceed_twin is False


def test_fair_grade_proceeds_twin():
    r = lookup_built_satisfaction(cv_mape=45.0, selection_n=20, asset_slice="commercial")
    assert r.grade == "fair"
    assert r.proceed_twin is True


def test_insufficient_cv():
    r = lookup_built_satisfaction(cv_mape=None, selection_n=30, asset_slice="commercial")
    assert r.grade == "insufficient_cv"
    assert r.proceed_twin is True


def test_factory_slice_more_lenient():
    r = lookup_built_satisfaction(cv_mape=40.0, selection_n=30, asset_slice="factory")
    assert r.grade in {"good", "fair"}


def test_grade_uses_worse_of_search_and_confirm():
    """등급은 탐색·확인 CV 중 나쁜 쪽으로 준다 (D-074).

    운영 해운대구 실측: 탐색 48.84 / 확인 79.83. 탐색으로 등급을 주면 확인 79.8%인
    모형이 「보통 ★★★」으로 나온다.
    """
    value, basis = grade_cv_basis(48.84, 79.83)
    assert value == 79.83
    assert basis == "confirm"

    worse = lookup_built_satisfaction(cv_mape=value, selection_n=700, asset_slice="commercial")
    optimistic = lookup_built_satisfaction(cv_mape=48.84, selection_n=700, asset_slice="commercial")
    assert worse.stars <= optimistic.stars


def test_grade_keeps_search_when_confirm_is_better():
    """확인이 더 좋게 나와도 등급을 올려 주지 않는다.

    운영 유성구 실측: 탐색 35.80 / 확인 22.92. 확인은 fold 1개라 그 해가 쉬웠을 뿐일 수
    있으므로 등급을 올리는 근거로 쓰지 않는다.
    """
    value, basis = grade_cv_basis(35.80, 22.92)
    assert value == 35.80
    assert basis == "search"


def test_grade_falls_back_to_available_cv():
    """한쪽만 있으면 그 값으로 등급을 준다 — 연도가 부족해도 등급은 나온다."""
    assert grade_cv_basis(25.2, None) == (25.2, "search")
    assert grade_cv_basis(None, 31.0) == (31.0, "confirm")
    assert grade_cv_basis(None, None) == (None, None)
