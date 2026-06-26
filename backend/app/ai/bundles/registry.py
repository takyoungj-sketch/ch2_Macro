"""Reasoning Bundle — panel → bundle_id 레지스트리."""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.schemas import AiApp, AiPurpose


@dataclass(frozen=True)
class BundleSpec:
    bundle_id: str
    description: str
    panels: tuple[str, ...]


BUNDLE_REGISTRY: dict[str, BundleSpec] = {
    "regression_diagnostic": BundleSpec(
        bundle_id="regression_diagnostic",
        description="회귀·VIF·상관·표본 진단",
        panels=("RegressionCard", "BuildingRegressionPanel", "LandRegressionTab"),
    ),
    "prediction_explain": BundleSpec(
        bundle_id="prediction_explain",
        description="예측값·신뢰구간 해석",
        panels=("PredictionCard", "PredictPanel"),
    ),
    "trend_diagnostic": BundleSpec(
        bundle_id="trend_diagnostic",
        description="장기추세·버킷·거래량",
        panels=("TrendCard", "LongTermTrendPanel"),
    ),
    "matrix_cell_explain": BundleSpec(
        bundle_id="matrix_cell_explain",
        description="매트릭스 칸·빈 셀·용도지역",
        panels=("MatrixCard", "PaidMatrixCell"),
    ),
    "floor_index_diagnostic": BundleSpec(
        bundle_id="floor_index_diagnostic",
        description="층별 효용지수·회귀 진단",
        panels=("FloorIndexPanel", "CommercialFloorIndexPanel"),
    ),
    "cluster_compare": BundleSpec(
        bundle_id="cluster_compare",
        description="코호트·클러스터 비교",
        panels=("CohortPanel", "CommercialClusterPanel"),
    ),
    "twin_city_compare": BundleSpec(
        bundle_id="twin_city_compare",
        description="Twin·유사 지역 비교",
        panels=("TwinRegionPanel", "ProfilePanel"),
    ),
}

PANEL_TO_BUNDLE: dict[str, str] = {}
for spec in BUNDLE_REGISTRY.values():
    for panel in spec.panels:
        PANEL_TO_BUNDLE[panel] = spec.bundle_id


SUGGESTED_QUESTIONS: dict[str, list[str]] = {
    "PredictionCard": [
        "예측값과 신뢰구간을 설명해 주세요.",
        "신뢰구간(PI)이 넓은 이유는?",
        "예측구간과 평균 신뢰구간 차이는?",
    ],
    "TrendCard": [
        "최근 상승 원인을 통계적으로 설명해 주세요.",
        "거래량 감소 패턴이 보이나요?",
        "변곡점은 언제인가요?",
        "장기추세를 요약해 주세요.",
    ],
    "BuildingRegressionPanel": [
        "이 결과를 어떻게 해석하나요?",
        "로그회귀와 선형회귀 차이는?",
        "신뢰구간이 넓은 이유는?",
        "모델 비교 권장값은?",
    ],
    "PaidMatrixCell": [
        "이 결과를 어떻게 해석하나요?",
        "면적 계수는 어떻게 봐야 하나요?",
        "신뢰구간이 넓은 이유는?",
        "표본수가 적으면 어떤 문제가 생기나요?",
    ],
    "RegressionCard": [
        "이 결과를 어떻게 해석하나요?",
        "왜 연식 계수가 음수인가요?",
        "신뢰구간이 넓은 이유는?",
        "Adj R²를 어떻게 봐야 하나요?",
        "VIF가 높으면 어떻게 하나요?",
    ],
    "MatrixCard": [
        "용도지역별 차이를 설명해 주세요.",
        "광평수 효과가 있나요?",
        "이 셀이 비어 있는 이유는?",
        "신뢰구간이 넓은 이유는?",
    ],
    "FloorIndexPanel": [
        "층별 지수를 어떻게 해석하나요?",
        "기준층은 어떻게 정해지나요?",
        "회귀 omitted category는 무엇인가요?",
    ],
}

PURPOSE_SUFFIX: dict[AiPurpose, str] = {
    "statistics": " (통계 해석)",
    "prediction": " (예측 해석)",
    "market_analysis": " (시장 패턴)",
    "methodology": " (방법론)",
}


def resolve_bundle_id(panel: str) -> str:
    return PANEL_TO_BUNDLE.get(panel, "regression_diagnostic")


def suggested_questions(
    panel: str,
    purpose: AiPurpose = "statistics",
    *,
    app: AiApp = "built",
) -> list[str]:
    base = list(SUGGESTED_QUESTIONS.get(panel, SUGGESTED_QUESTIONS["RegressionCard"]))
    if app == "land" and panel in ("MatrixCard", "PaidMatrixCell"):
        base = [
            "용도지역별 차이를 설명해 주세요.",
            "광평수 효과가 있나요?",
            "신뢰구간이 넓은 이유는?",
            "이 칸의 표본을 설명해 주세요.",
        ]
    _ = PURPOSE_SUFFIX.get(purpose, "")
    return base[:6]
