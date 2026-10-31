"""공통 표본 판정. 30건·계수당 5건은 분석 제공 기준이다."""

import numpy as np

from app.regression_sample_judge import (
    MissingFunnel,
    blocked_reasons,
    design_nullspace,
    identification_note,
    is_computable,
    judge_sample,
    prediction_is_identified,
    provision_note,
    residual_df,
    sample_notes,
    unidentified_column_names,
)


def test_residual_df_uses_rank_not_column_count():
    assert residual_df(25, 4) == 21
    assert residual_df(25, 6) == 19


def test_zero_residual_df_is_not_computable():
    assert blocked_reasons(10, 10) == ("잔차 자유도 없음",)
    assert is_computable(10, 9)
    assert judge_sample(10, 10, 10).tier == "blocked"


def test_rank_below_one_is_not_computable():
    assert blocked_reasons(12, 0) == ("설계행렬 계수 없음",)
    assert judge_sample(12, 0, 4).tier == "blocked"


def test_rank_gap_is_still_computable_and_can_be_standard():
    # 열 17, 계수 14, 잔차 자유도 98. 112/14 ≥ 5 이면 일반이고 식별만 따로 표시한다.
    verdict = judge_sample(112, 14, 17)
    assert is_computable(112, 14)
    assert residual_df(112, 14) == 98
    assert verdict.tier == "standard"
    assert verdict.identification
    assert sample_notes(verdict) == [
        "모형 식별: 설계 열 17개, 독립 계수 14개. 계수가 한 값으로 정해지지 않습니다."
    ]


def test_caution_when_either_bar_fails():
    few_rows = judge_sample(20, 4, 4)
    assert few_rows.tier == "caution"
    assert provision_note(few_rows) == "분석 제공 기준(30건, 계수당 5건)에 못 미쳐 참고용"

    thin = judge_sample(40, 10, 10)
    assert thin.tier == "caution"
    assert not thin.identification

    both = judge_sample(18, 6, 6)
    assert both.tier == "caution"


def test_standard_needs_both_bars():
    verdict = judge_sample(40, 8, 8)
    assert verdict.tier == "standard"
    assert sample_notes(verdict) == []
    assert identification_note(verdict) is None


def test_regional_unit_uses_complexes():
    verdict = judge_sample(28, 5, 5)
    assert verdict.tier == "caution"
    assert provision_note(verdict, unit="곳") == "분석 제공 기준(30곳, 계수당 5곳)에 못 미쳐 참고용"


def test_funnel_identity():
    funnel = MissingFunnel(
        n_source=100,
        n_excluded_target=5,
        n_excluded_numeric=30,
        n_excluded_categorical=0,
        n_fit=65,
    )
    assert funnel.balances()


def test_nullspace_of_a_tall_copy_does_not_need_a_square_factor():
    base = np.array([[1.0, 0.0], [1.0, 1.0], [1.0, 2.0], [1.0, 3.0]])
    tall = np.column_stack([base, base[:, 1]])
    assert unidentified_column_names(tall, ["a", "b", "b2"]) == {"b", "b2"}
    wide = tall[:2]
    assert unidentified_column_names(wide, ["a", "b", "b2"]) == {"b", "b2"}
    assert design_nullspace(tall).shape[0] == 1


def test_wide_rank_deficiency_is_not_hidden_by_a_gram_matrix():
    rng = np.random.default_rng(0)
    basis, _r = np.linalg.qr(rng.normal(size=(40, 20)))
    extra = basis @ rng.normal(size=(20, 21))
    exog = np.column_stack([basis, extra])
    null = design_nullspace(exog)
    assert null.shape == (21, 41)
    assert prediction_is_identified(exog, exog[0])
    assert not prediction_is_identified(exog, exog[0] + null[0])
