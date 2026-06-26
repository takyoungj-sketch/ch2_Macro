"""복합(built) 회귀 — AI Explain presets · 해석 템플릿."""

from __future__ import annotations

from typing import Any

from app.ai.built_narrative import NarrativeResult, build_built_narrative
from app.ai.schemas import AnalysisExplain, AnalysisExplainPreset


def built_regression_explain_from_facts(facts: dict[str, Any]) -> AnalysisExplain:
    """회귀 API 응답 → AnalysisExplain (집합 analysis_explain 동형)."""
    primary = facts.get("primary") if isinstance(facts.get("primary"), dict) else facts
    scope = (primary or {}).get("scope_label") or "선택 scope"
    n = (primary or {}).get("n")
    return AnalysisExplain(
        spec_id="built_regression_v1",
        spec_version="1",
        title="복합부동산 OLS 회귀",
        summary=(
            f"{scope} 거래 표본을 바탕으로 금액(또는 log 금액)에 대한 OLS 회귀를 추정합니다. "
            "계수는 다른 변수를 통제한 조건에서의 **패턴**이며, 인과·적정가격을 의미하지 않습니다."
        ),
        formula="금액(또는 log 금액) ~ 연면적·대지·연식·용도·도로 등 (scope·표본 필터 동일)",
        interpretation=[
            "Adj R²: 모형이 가격 변동을 설명하는 **참고** 비율입니다. 높을수록 설명력은 크지만, 표본·변수 선택에 민감합니다.",
            "유의한 계수(p<0.05): 해당 변수와 금액 간 **통계적 연관**이 scope 내에서 관찰됨을 뜻합니다.",
            "상관·산점도: 단순 관계를 보조합니다. 회귀는 다변량 통제 후 계수입니다.",
            "VIF: 연속 변수 간 다중공선성 참고. 10 이상이면 계수 해석에 주의.",
        ],
        limitations=[
            "선택 기간·지역·필터 안의 거래만 사용합니다.",
            "표본·이상치·누락 변수에 따라 계수 부호가 바뀔 수 있습니다.",
            "감정평가·투자·적정가격 판단이 아닙니다.",
        ],
        presets=[
            AnalysisExplainPreset(
                id="interpret",
                question="이 결과를 어떻게 해석하나요?",
                answer="",  # 동적 생성 — interpret_built_regression
            ),
            AnalysisExplainPreset(
                id="adj_r2",
                question="Adj R²를 어떻게 봐야 하나요?",
                answer=(
                    "Adj R²는 변수 개수를 고려한 설명력 지표입니다. "
                    "0.8 전후면 scope 내에서 상당 부분의 가격 변동이 모형 변수와 연관되어 있음을 **참고**할 수 있으나, "
                    "예측 정확도·인과·외부 유효성을 단독으로 보장하지 않습니다."
                ),
            ),
            AnalysisExplainPreset(
                id="vif",
                question="VIF가 높으면 어떻게 하나요?",
                answer=(
                    "VIF≥10 변수가 있으면 다른 설명변수와 강하게 겹친 상태일 수 있습니다. "
                    "해당 변수 계수(예: 연식)의 부호·크기를 단독으로 해석하지 말고, "
                    "변수 축소·모형 단순화·상관 행렬을 함께 보세요."
                ),
            ),
        ],
    )


def built_prediction_explain(*, scope_label: str) -> AnalysisExplain:
    return AnalysisExplain(
        spec_id="built_prediction_v1",
        spec_version="1",
        title="복합부동산 회귀 예측",
        summary=(
            f"**{scope_label}** scope OLS 모형으로 입력 조건의 **통계적 예측금액**과 "
            "95% 예측구간(PI)·평균 신뢰구간(CI)을 산출합니다. **적정가가 아닙니다.**"
        ),
        formula="ŷ = Xβ (동일 scope 회귀 계수) · PI = 개별 거래 · CI = 평균 예측",
        interpretation=[
            "PI: 이 조건과 유사한 개별 거래 1건이 들어올 법한 범위.",
            "CI: 평균 예측값의 불확실성(개별 변동 제외).",
            "n이 작거나 Adj R²가 낮으면 PI가 넓어집니다.",
        ],
        limitations=[
            "탐색용 OLS 출력이며 감정·투자 판단이 아닙니다.",
            "입력값이 scope 밖이면 예측이 불안정할 수 있습니다.",
        ],
        presets=[
            AnalysisExplainPreset(
                id="interpret",
                question="이 결과를 어떻게 해석하나요?",
                answer="",
            ),
            AnalysisExplainPreset(
                id="pi",
                question="신뢰구간(PI)이 넓은 이유는?",
                answer="",
            ),
        ],
    )


def interpret_built_regression(
    *,
    diagnostics: dict[str, Any],
    scope_label: str,
    message: str = "",
    correlations: list[dict[str, Any]] | None = None,
) -> NarrativeResult:
    """CH2 Facts + Bundle diagnostics → 2세대 내러티브 (No Recalculation)."""
    return build_built_narrative(
        diagnostics=diagnostics,
        scope_label=scope_label,
        message=message,
        correlations=correlations,
    )
