"""복합 점검 4단계 (2026-11-11) — RS-2 · B-08 · T-5 · F-1 보강 · B-01 문구.

화면 문구만 바꾼 항목(B-04·B-07·A-4·B-10·연결률)은 프론트 타입체크로 확인한다.
"""

from __future__ import annotations

import pandas as pd

from app.recommendation.twin_structure import CONFIRM_FALLBACK_MIN_N, decide_twin_prefix
from app.recommendation.twin_validation import build_twin_validation_verdict


# ── RS-2 ─────────────────────────────────────────────────────────────────────


def test_tx_label_skips_nan_lot():
    from app.built.regression.residuals import _tx_label

    assert _tx_label(pd.Series({"addr4": "복대동", "addr5": float("nan")}), "addr4") == "복대동"
    assert _tx_label(pd.Series({"addr4": "복대동", "addr5": None}), "addr4") == "복대동"
    assert _tx_label(pd.Series({"addr4": "복대동", "addr5": "123-4"}), "addr4") == "복대동 123-4"
    assert _tx_label(pd.Series({"addr4": None, "addr5": float("nan")}), "addr4") == "주소 미상"


# ── B-08 ─────────────────────────────────────────────────────────────────────


def test_built_evidence_rounds_r2_and_korean_asset_type():
    from app.ai.dialogue import ScreenEvidence, _built_regression, _built_term

    ev = ScreenEvidence(context={})
    _built_regression(ev, {"primary": {"n": 102, "r_squared": 0.88287312, "adj_r_squared": 0.8712345,
                                       "mape": 27.4123, "coefficients": [],
                                       "predict_options": {"asset_type_reference": "commercial"}}})
    assert "R² 0.883" in ev.facts and "조정 R² 0.871" in ev.facts
    assert "학습 MAPE 27.41%" in ev.facts
    assert any("유형 기준 범주 상업업무" in n for n in ev.notes)
    assert _built_term("atype_detached", "linear") == "유형 단독다가구"


def test_calc_caution_is_property_term_outside_land():
    from app.ai.dialogue import _calc_caution

    assert "토지" in _calc_caution("land")
    built = _calc_caution("built")
    assert "토지의 적정가격" not in built and "부동산의 적정가격" in built


def test_scope_asset_type_is_korean():
    from app.ai.dialogue import _screen
    from app.ai.schemas import AiContext

    ev = _screen(AiContext(app="built", panel="RegressionCard", facts={}, scope={"asset_type": "commercial,detached"}))
    assert ev.context["scope"]["asset_type"] == "상업업무·단독다가구"


# ── T-5 ──────────────────────────────────────────────────────────────────────


def _row(confirm_n: int, *, local_confirm=33.49, twin_confirm=20.0, n=102):
    return {"candidate_id": "twin_selected", "label": "Local + 1곳", "prefix_k": 1, "n": n,
            "blocks": ["gross_area", "region_leaf"], "scored_on": "anchor_common",
            "search_cv_mape": None, "search_eval_n": 45, "local_search_cv_mape": None,
            "confirm_cv_mape": twin_confirm, "confirm_eval_n": confirm_n,
            "local_confirm_cv_mape": local_confirm, "local_confirm_eval_n": confirm_n,
            "key_coefficients": {}}


def _decide(row):
    return decide_twin_prefix(local_n=72, local_search_cv=None, local_confirm_cv=row["local_confirm_cv_mape"],
                              local_coeffs={}, local_blocks=["gross_area"], prefixes=[row])


def test_confirm_fallback_needs_ten_trades():
    d = _decide(_row(CONFIRM_FALLBACK_MIN_N - 1))
    assert d.judgment_basis == "none" and d.search_band == "unavailable"
    assert d.decision == "local" and "판정 보류" in d.judgment_basis_ko
    v = build_twin_validation_verdict(ran=True, skipped_reason=None, local_cv_mape=None, decision=d.decision,
                                      primary=None, pools=[], prefix=d)
    assert v.verdict == "unavailable" and v.judgment_basis == "none"


def test_confirm_fallback_judges_when_enough_trades():
    d = _decide(_row(CONFIRM_FALLBACK_MIN_N))
    assert d.judgment_basis == "confirm_cv"
    assert d.adopt_recommended and d.decision == "twin_selected"
    assert "확인 CV 기준" in d.judgment_basis_ko
    v = build_twin_validation_verdict(ran=True, skipped_reason=None, local_cv_mape=None, decision=d.decision,
                                      primary=None, pools=[], prefix=d)
    assert v.verdict == "improved" and v.judgment_basis == "confirm_cv"

    worse = _decide(_row(20, twin_confirm=45.0))
    assert worse.judgment_basis == "confirm_cv" and worse.search_band == "worse" and worse.decision == "local"


def test_search_cv_stays_primary_basis():
    row = _row(30)
    row.update(search_cv_mape=20.0, local_search_cv_mape=30.0, search_eval_n=40, local_search_eval_n=40)
    d = decide_twin_prefix(local_n=72, local_search_cv=30.0, local_confirm_cv=33.49, local_coeffs={},
                           local_blocks=["gross_area"], prefixes=[row])
    assert d.judgment_basis == "search_cv"


# ── F-1 보강 · B-01 문구 ──────────────────────────────────────────────────────


def test_backfill_skips_approval_after_contract():
    from app.built.regression.age_backfill import LEDGER_AGE_FLAG, backfill_age_from_ledger

    out = backfill_age_from_ledger(pd.DataFrame(
        {"building_age": [None, None], "approve_year": [2025, 2024], "contract_year": [2023, 2024]}
    ))
    assert pd.isna(out["building_age"].iloc[0]) and not out[LEDGER_AGE_FLAG].iloc[0]  # 0 클립 금지
    assert out["building_age"].iloc[1] == 0


def test_negative_estimate_wording_drops_extrapolation():
    from app.built.regression.engine import NONPOSITIVE_ESTIMATE_WARNING

    assert "선형식 계산 결과이며 실제 거래금액을 의미하지 않습니다" in NONPOSITIVE_ESTIMATE_WARNING
    assert "외삽" not in NONPOSITIVE_ESTIMATE_WARNING
