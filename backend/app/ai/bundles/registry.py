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
    "rent_conversion": BundleSpec(
        bundle_id="rent_conversion",
        description="주거 전월세 전환율·환산 P50",
        panels=("RentListCard",),
    ),
    "sangkwon_reb": BundleSpec(
        bundle_id="sangkwon_reb",
        description="부동산원 상업용 임대동향 상권 공표",
        panels=("SangkwonCard",),
    ),
    "recommend_diagnostic": BundleSpec(
        bundle_id="recommend_diagnostic",
        description="모형 탐색 판정·Twin·권장 행동",
        panels=("RecommendationCard", "ModelSelectionCard"),
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
        "이번 표본에서 설명력이 제한적인 이유는?",
        "왜 연식 계수가 음수인가요?",
        "신뢰구간이 넓은 이유는?",
        "VIF가 높을 때 이 계수를 어떻게 읽나요?",
    ],
    "RecommendationCard": [
        "AI 진단을 요약해 주세요.",
        "왜 예측이 부적합한가요?",
        "Twin을 써도 안 되면 어떻게 하나요?",
        "다음에 무엇을 하면 좋나요?",
        "설명형 회귀는 어떻게 활용하나요?",
    ],
    "MatrixCard": [
        "용도지역별 차이를 설명해 주세요.",
        "광평수 효과가 있나요?",
        "이 셀이 비어 있는 이유는?",
        "신뢰구간이 넓은 이유는?",
    ],
    "RentListCard": [
        "왜 단순평균 전환율인가요?",
        "적용 전환율은 공식값인가요?",
        "전세전환값은 시세인가요?",
        "연립은 왜 편차가 큰가요?",
        "읍면동 전환율이 없을 때는?",
    ],
    "SangkwonCard": [
        "임대료와 임대수입이 다른 이유는?",
        "연간 임대료는 어떻게 환산하나요?",
        "공실률을 NOI에 곱하면 안 되는 이유는?",
        "연간 투자수익률은 평균인가요 복리인가요?",
        "이 상권 공표는 주거 전월세와 같나요?",
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

PURPOSE_QUESTION_OVERRIDES: dict[AiPurpose, dict[str, list[str]]] = {
    "methodology": {
        "RegressionCard": [
            "로그회귀와 선형회귀 차이는?",
            "이 scope에서 변수 선택 trade-off는?",
            "VIF가 높을 때 모형을 어떻게 읽나요?",
            "표본 n이 적을 때 spec을 어떻게 보나요?",
        ],
        "BuildingRegressionPanel": [
            "로그회귀와 선형회귀 차이는?",
            "고정효과(FE)를 쓰는 이유는?",
            "모형 spec trade-off를 설명해 주세요.",
        ],
        "RentListCard": [
            "왜 단순평균 전환율인가요?",
            "적용 전환율은 공식값인가요?",
            "전세전환값은 시세인가요?",
            "연립은 왜 편차가 큰가요?",
        ],
        "SangkwonCard": [
            "임대료와 임대수입이 다른 이유는?",
            "연간 임대료·순영업소득은 어떻게 만드나요?",
            "공실률을 NOI에 곱하면 안 되는 이유는?",
            "연간 수익률 복리 연결은 무엇인가요?",
        ],
    },
    "prediction": {
        "PredictionCard": [
            "예측값과 신뢰구간을 설명해 주세요.",
            "PI가 넓은 이유는?",
            "이 scope 예측의 한계는?",
        ],
        "RegressionCard": [
            "이 회귀 결과로 예측할 때 주의할 점은?",
            "in-sample MAPE를 어떻게 읽나요?",
            "표본 밖 예측 불확실성은?",
        ],
    },
    "market_analysis": {
        "TrendCard": [
            "최근 상승 원인을 통계적으로 설명해 주세요.",
            "거래량 감소 패턴이 보이나요?",
            "변곡점은 언제인가요?",
            "장기추세를 요약해 주세요.",
        ],
        "RegressionCard": [
            "이 scope의 가격 패턴 요약은?",
            "유의 변수가 시사하는 것은?",
            "거래량·시기 필터 영향은?",
        ],
    },
}


def resolve_bundle_id(panel: str) -> str:
    return PANEL_TO_BUNDLE.get(panel, "regression_diagnostic")


def suggested_questions(
    panel: str,
    purpose: AiPurpose = "statistics",
    *,
    app: AiApp = "built",
) -> list[str]:
    purpose_map = PURPOSE_QUESTION_OVERRIDES.get(purpose, {})
    if panel in purpose_map:
        base = list(purpose_map[panel])
    else:
        base = list(SUGGESTED_QUESTIONS.get(panel, SUGGESTED_QUESTIONS["RegressionCard"]))
    if app == "land" and panel in ("MatrixCard", "PaidMatrixCell") and purpose == "statistics":
        base = [
            "용도지역별 차이를 설명해 주세요.",
            "광평수 효과가 있나요?",
            "신뢰구간이 넓은 이유는?",
            "이 칸의 표본을 설명해 주세요.",
        ]
    suffix = PURPOSE_SUFFIX.get(purpose, "")
    if suffix and purpose == "statistics":
        return base[:6]
    if suffix and purpose != "statistics":
        # methodology/prediction/market_analysis는 전용 목록 사용 — suffix는 UI 탭 라벨만
        return base[:6]
    return base[:6]
