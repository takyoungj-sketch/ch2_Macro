"""탐색 1위를 대표모형으로 확정하지 않는 화면 규칙. 순위는 바꾸지 않는다."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.built.regression.selection.fit import BlockFitResult, CvPhase
from app.built.schemas import RegressionVariableSpec
from app.recommendation.ranks import representative_verdict


def _fit(search: CvPhase, confirm: CvPhase) -> BlockFitResult:
    return BlockFitResult(
        blocks=[],
        variables=RegressionVariableSpec(),
        response_scale="linear",
        n=44,
        n_params=13,
        aic=0.0,
        bic=0.0,
        adj_r_squared=None,
        mape=39.06,
        model=None,
        x_const=pd.DataFrame(),
        y_price=np.array([]),
        joint_f_tests={},
        cv_mape=search.mape,
        cv_folds=search.folds,
        confirm_cv_mape=confirm.mape,
        confirm_cv_folds=confirm.folds,
        cv_search=search,
        cv_confirm=confirm,
    )


def test_single_year_and_worse_confirm_withholds_representative():
    search = CvPhase(mape=8.13, folds=1, n_trades=4, years=(2025,), held_years=(2025,))
    confirm = CvPhase(mape=36.98, folds=1, n_trades=9, years=(2026,), held_years=(2026,))
    confirmed, note = representative_verdict(_fit(search, confirm))
    assert confirmed is False
    assert note is not None
    assert "대표모형은 확정하지 않았습니다" in note
    assert "2025년" in note
    assert "4건" in note
    assert "36.98%" in note


def test_multi_year_close_confirm_is_representative():
    search = CvPhase(
        mape=12.0, folds=3, n_trades=40, years=(2022, 2023, 2024), held_years=(2022, 2023, 2024)
    )
    confirm = CvPhase(mape=14.0, folds=1, n_trades=12, years=(2025,), held_years=(2025,))
    confirmed, note = representative_verdict(_fit(search, confirm))
    assert confirmed is True
    assert note is None


def test_large_confirm_gap_withholds_even_when_search_is_wide():
    search = CvPhase(
        mape=10.0, folds=3, n_trades=40, years=(2022, 2023, 2024), held_years=(2022, 2023, 2024)
    )
    confirm = CvPhase(mape=25.0, folds=1, n_trades=12, years=(2025,), held_years=(2025,))
    confirmed, note = representative_verdict(_fit(search, confirm))
    assert confirmed is False
    assert note is not None
    assert "15.0%p" in note


def test_one_year_withholds_even_when_that_year_has_many_trades():
    search = CvPhase(mape=10.0, folds=1, n_trades=40, years=(2025,), held_years=(2025,))
    confirm = CvPhase(mape=11.0, folds=1, n_trades=12, years=(2026,), held_years=(2026,))
    confirmed, note = representative_verdict(_fit(search, confirm))
    assert confirmed is False
    assert note is not None
    assert "2025년 40건" in note


def test_failed_search_year_withholds_even_when_two_folds_succeed():
    search = CvPhase(
        mape=8.0,
        folds=2,
        n_trades=30,
        years=(2022, 2024),
        held_years=(2022, 2023, 2024),
        failure_reasons=((2023, "학습 표본 부족"),),
    )
    confirm = CvPhase(mape=9.0, folds=1, n_trades=12, years=(2025,), held_years=(2025,))
    confirmed, note = representative_verdict(_fit(search, confirm))
    assert confirmed is False
    assert note is not None
    assert "2023년" in note
    assert "완료하지 못했습니다" in note


def test_unscored_confirm_year_withholds():
    search = CvPhase(
        mape=12.0, folds=2, n_trades=20, years=(2023, 2024), held_years=(2023, 2024)
    )
    confirm = CvPhase(held_years=(2025,))
    confirmed, note = representative_verdict(_fit(search, confirm))
    assert confirmed is False
    assert note is not None
    assert "확인을 계산하지 못했습니다" in note
