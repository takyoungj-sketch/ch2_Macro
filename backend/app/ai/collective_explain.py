"""집합(collective) — analysis_explain → AI Explain."""

from __future__ import annotations

from typing import Any, Optional

from app.ai.schemas import AnalysisExplain, AnalysisExplainPreset
from app.collective.analysis_explain import _preset_answers_residential_regression


def _to_analysis_explain(raw: dict[str, Any]) -> AnalysisExplain:
    presets = [
        AnalysisExplainPreset(id=p["id"], question=p["question"], answer=p["answer"])
        for p in raw.get("presets") or []
        if isinstance(p, dict)
    ]
    return AnalysisExplain(
        spec_id=str(raw.get("spec_id") or "collective_explain"),
        spec_version=str(raw.get("spec_version") or "1"),
        title=str(raw.get("title") or "집합부동산 분석"),
        summary=str(raw.get("summary") or ""),
        formula=raw.get("formula"),
        interpretation=list(raw.get("interpretation") or []),
        limitations=list(raw.get("limitations") or []),
        presets=presets,
        controls=list(raw.get("controls") or []),
        floor_groups=list(raw.get("floor_groups") or []),
    )


def collective_regression_explain_from_context(
    *,
    asset_type: str = "apartment",
    cohort: bool = False,
    explain_payload: Optional[dict[str, Any]] = None,
) -> AnalysisExplain:
    if explain_payload:
        return _to_analysis_explain(explain_payload)
    presets = [
        AnalysisExplainPreset(id=p["id"], question=p["question"], answer=p["answer"])
        for p in _preset_answers_residential_regression(asset_type=asset_type, cohort=cohort)
    ]
    scope = "코호트(복수 단지)" if cohort else "단일 단지"
    return AnalysisExplain(
        spec_id=f"collective_regression_{asset_type}_v1",
        spec_version="1",
        title="집합부동산 회귀 분석",
        summary=(
            f"{scope} 내 거래금액(만원) OLS 회귀입니다. "
            "변수·층 형식 선택에 따라 결과가 달라지는 **탐색용** 분석이며, "
            "인과·적정가·투자 판단을 의미하지 않습니다."
        ),
        formula="금액(만원) ~ 전용면적·연식·층·동 등 (단지·기간 scope 동일)",
        interpretation=[
            "Adj R²: 모형 설명력 참고치.",
            "유의 계수: scope 내 통계적 연관.",
            "로그/선형 모델 비교는 model_comparison 권장값을 참고하세요.",
        ],
        limitations=[
            "단지(또는 코호트) 내 표본에 한정.",
            "층·동 효용지수 탭과 spec이 다릅니다.",
            "감정평가·투자 판단이 아닙니다.",
        ],
        presets=presets,
    )
