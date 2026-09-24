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
        description="통계적 추정값·추정범위 해석",
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
        description="지역프로필 Twin(algo 21) · 복합 Stage2 검증. 토지 레거시 모달 없음",
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
    "insight_macro_01": BundleSpec(
        bundle_id="insight_macro_01",
        description="Macro Insight 1번 — 전국 월 금리·M2 × 거래",
        panels=("Insight01", "InsightHome"),
    ),
    "insight_macro_02": BundleSpec(
        bundle_id="insight_macro_02",
        description="Macro Insight 2번 — 시군구 유형 규모·단가 상관",
        panels=("Insight02",),
    ),
    "insight_macro_03": BundleSpec(
        bundle_id="insight_macro_03",
        description="Macro Insight 3번 — 연립·다세대 층×승강기",
        panels=("Insight03",),
    ),
    "insight_macro_04": BundleSpec(
        bundle_id="insight_macro_04",
        description="Macro Insight 4번 — 토지 면적×㎡당 가격",
        panels=("Insight04",),
    ),
    "insight_macro_05": BundleSpec(
        bundle_id="insight_macro_05",
        description="Macro Insight 5번 — 연 거래액 vs GDP·M2·주식·유형 구성",
        panels=("Insight05",),
    ),
    "insight_macro_06": BundleSpec(
        bundle_id="insight_macro_06",
        description="Macro Insight 6번 — 도로 지목 상대가격",
        panels=("Insight06",),
    ),
    "insight_macro_07": BundleSpec(
        bundle_id="insight_macro_07",
        description="Macro Insight 7번 — 쌍둥이 지역을 고르는 방법",
        panels=("Insight07",),
    ),
    "insight_macro_08": BundleSpec(
        bundle_id="insight_macro_08",
        description="Macro Insight 8번 — 아파트 층 효용의 지역·높이",
        panels=("Insight08",),
    ),
    "insight_macro_10": BundleSpec(
        bundle_id="insight_macro_10",
        description="Macro Insight 10번 — 집합상가 도로 안의 1층과 2층",
        panels=("Insight10",),
    ),
    "insight_macro_11": BundleSpec(
        bundle_id="insight_macro_11",
        description="Macro Insight 11번 — 5년 수익률과 국고채·코스피",
        panels=("Insight11",),
    ),
    "list_overview": BundleSpec(
        bundle_id="list_overview",
        description="기본통계 목록·매트릭스 화면 안내",
        panels=("BuildingList", "CommercialList", "CollectiveLanding"),
    ),
}

PANEL_TO_BUNDLE: dict[str, str] = {}
for spec in BUNDLE_REGISTRY.values():
    for panel in spec.panels:
        PANEL_TO_BUNDLE[panel] = spec.bundle_id


SUGGESTED_QUESTIONS: dict[str, list[str]] = {
    "PredictionCard": [
        "통계적 추정값을 설명해 주세요.",
        "예측값과 신뢰구간을 설명해 주세요.",
        "개별 거래 예측범위가 넓은 이유는?",
        "평균 추정범위와 개별 거래 예측범위 차이는?",
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
        "이 표의 칸은 무엇을 뜻하나요?",
        "칸을 클릭하면 무엇이 나오나요?",
        "필터 분석과 무엇이 다른가요?",
        "n이 작은 칸은 어떻게 읽나요?",
    ],
    "BuildingList": [
        "이 표의 열은 무엇을 뜻하나요?",
        "단지를 클릭하면 무엇이 나오나요?",
        "지역회귀는 언제 쓰나요?",
        "세대수는 어떻게 읽나요?",
    ],
    "CommercialList": [
        "도로명 열은 무엇을 뜻하나요?",
        "도로를 클릭하면 무엇이 나오나요?",
        "n<15은 어떻게 읽나요?",
        "주거 단지 표와 무엇이 다른가요?",
    ],
    "CollectiveLanding": [
        "주거와 상업·업무는 무엇이 다른가요?",
        "통계분석은 어디서 하나요?",
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
        "예측 오차는 어떻게 읽나요?",
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
    "ProfilePanel": [
        "이 지역 프로필을 요약해 주세요.",
        "8대 시장 구성은 어떻게 읽나요?",
        "쌍둥이 지역은 어떻게 고르나요?",
        "토지 Top3와 아파트 분위는 무엇인가요?",
        "프로필 3년 창과 토지 롤링 창이 다른 이유는?",
    ],
    "TwinRegionPanel": [
        "이 쌍둥이 지역은 왜 뽑혔나요?",
        "유사도는 어떤 지표로 계산하나요?",
        "쌍둥이 지역을 회귀에 넣어도 되나요?",
        "시군구 Twin과 읍면동 Twin 범위 차이는?",
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
    "Insight01": [
        "상관계수가 뭔가요?",
        "왜 금액 그래프만 보면 안 되나요?",
        "합계는 모든 부동산인가요?",
        "한 달 뒤는 무슨 뜻인가요?",
        "금리가 거래를 줄인 건가요?",
    ],
    "Insight02": [
        "이 숫자는 시간에 따라 같이 움직인다는 뜻인가요?",
        "인구 보정은 무엇을 빼나요?",
        "거래규모와 거래건수는 왜 다른가요?",
        "가격 수준 표는 규모 표와 같은가요?",
        "같이 크면 원인이 있는 건가요?",
    ],
    "Insight03": [
        "1층=100은 시세 100인가요?",
        "승강기를 설치하면 13% 오르나요?",
        "26%와 13.5%를 더하면 되나요?",
        "아파트 층 지수와 같은가요?",
        "이 숫자를 단지 가격에 써도 되나요?",
    ],
    "Insight04": [
        "약 −20%는 전국 광평 할인율인가요?",
        "대지는 큰 땅일수록 비싼가요?",
        "광평은 1,000㎡ 이상인가요?",
        "토지 회귀 면적 계수와 같은가요?",
        "같은 동 안에서도 남나요?",
    ],
    "Insight05": [
        "부동산이 GDP의 몇 퍼센트인가요?",
        "시중 돈이 부동산으로 간 건가요?",
        "주식이 대체된 건가요?",
        "일정한 관계가 성립하나요?",
        "1번 글과 무엇이 다른가요?",
    ],
    "Insight06": [
        "도로 땅은 대지의 3분의 1인가요?",
        "도시에서는 몇 %인가요?",
        "지목 도로는 평가에서 말하는 도로인가요?",
        "논·밭과 비교하면 왜 더 높은가요?",
        "토지 회귀식과 같은 숫자인가요?",
    ],
    "Insight07": [
        "91.4%면 그 지역과 91.4% 같나요?",
        "읍면동은 전국에서 찾나요?",
        "n=3은 거래가 3건인가요?",
        "임대도 보나요?",
        "이 점수로 가격을 맞추나요?",
    ],
    "Insight08": [
        "1층=100은 시세 100인가요?",
        "비도시 최상층이 더 싼가요?",
        "26층부터 달라지나요?",
        "오피스텔도 같나요?",
        "가운데값과 ④의 %는 같은 숫자인가요?",
    ],
    "Insight10": [
        "1층=100은 시세 100인가요?",
        "55와 68 중 어느 쪽인가요?",
        "왜 2층이 싼가요?",
        "아파트 108과 더하면 되나요?",
        "다른 지역도 같나요?",
    ],
    "Insight11": [
        "투자수익률과 소득+자본은 같은 숫자인가요?",
        "아파트 현금 월세가 국고채보다 낮은가요?",
        "KODEX는 KRX 총수익 지수인가요?",
        "오피스는 오피스텔인가요?",
        "어느 쪽이 더 나은 투자인가요?",
    ],
    "InsightHome": [
        "Macro Insight는 무엇인가요?",
        "이 창은 분석 앱인가요?",
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
            "통계적 추정값을 설명해 주세요.",
            "개별 거래 예측범위가 넓은 이유는?",
            "이 scope 추정의 한계는?",
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
    if app == "insight":
        if panel == "Insight05":
            base = list(SUGGESTED_QUESTIONS["Insight05"])
        elif panel == "Insight06":
            base = list(SUGGESTED_QUESTIONS["Insight06"])
        elif panel == "Insight11":
            base = list(SUGGESTED_QUESTIONS["Insight11"])
        elif panel == "Insight10":
            base = list(SUGGESTED_QUESTIONS["Insight10"])
        elif panel == "Insight08":
            base = list(SUGGESTED_QUESTIONS["Insight08"])
        elif panel == "Insight07":
            base = list(SUGGESTED_QUESTIONS["Insight07"])
        elif panel == "Insight04":
            base = list(SUGGESTED_QUESTIONS["Insight04"])
        elif panel == "Insight03":
            base = list(SUGGESTED_QUESTIONS["Insight03"])
        elif panel == "Insight02":
            base = list(SUGGESTED_QUESTIONS["Insight02"])
        elif panel in ("Insight01", "InsightHome"):
            base = list(SUGGESTED_QUESTIONS.get(panel, SUGGESTED_QUESTIONS["Insight01"]))
    suffix = PURPOSE_SUFFIX.get(purpose, "")
    if suffix and purpose == "statistics":
        return base[:6]
    if suffix and purpose != "statistics":
        # methodology/prediction/market_analysis는 전용 목록 사용 — suffix는 UI 탭 라벨만
        return base[:6]
    return base[:6]
