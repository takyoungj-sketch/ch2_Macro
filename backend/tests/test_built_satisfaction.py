"""R2 — satisfaction grade lookup."""

from __future__ import annotations

from app.recommendation.satisfaction import lookup_built_satisfaction


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
