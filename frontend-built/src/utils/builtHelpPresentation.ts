import type { AnalysisExplain } from "@ch2/analysis-help";

type Intro = { title?: string; summary: string; points: string[]; notes?: string[] };
const regression: Intro = {
  title: "기본회귀 결과 읽기", summary: "선택한 지역과 기간의 거래로 금액과 여러 조건의 관계를 분석한 결과입니다.",
  points: ["결과 요약에서 적합도와 오차를 확인해 주세요. 실제 반영된 변수는 회귀식과 계수 표에서 볼 수 있습니다.", "학습 MAPE는 분석에 사용한 거래의 오차입니다. CV-MAPE는 과거 연도로 학습해 다음 연도 거래를 예측한 오차입니다.", "산점도와 잔차 진단에서는 변수의 관계와 오차가 큰 조건을 확인할 수 있습니다."],
  notes: ["계수는 통계적 관계이며 인과관계나 개별 부동산의 적정가격을 뜻하지 않습니다.", "지역·기간·필터·변수에 따라 결과가 달라집니다. 서로 다른 표본의 지표만으로 모형의 우열을 판단하지 마세요."],
};
const prediction: Intro = {
  title: "조건별 추정 읽기", summary: "입력한 조건을 현재 회귀모형에 적용한 통계적 참고값입니다. AVM에 의한 가격평가나 감정평가액이 아닙니다.",
  points: ["추정금액은 입력 조건에서 모형이 계산한 중심값입니다.", "95% 평균 추정범위는 같은 조건의 평균적인 금액 수준에 대한 불확실성을 나타냅니다.", "95% 개별 거래 예측범위는 거래마다 생기는 변동까지 포함하므로 평균 추정범위보다 넓을 수 있습니다."],
  notes: ["실제 거래금액이 표시된 범위에 반드시 포함되는 것은 아닙니다.", "학습 자료에서 벗어난 면적·연식 등의 조건은 추정이 불안정할 수 있습니다."],
};
export const BUILT_HELP_INTROS: Record<string, Intro> = {
  built_regression_static_v1: regression, built_regression_v1: regression,
  built_prediction_static_v1: prediction, built_prediction_v1: prediction,
  built_scatter_raw_v1: { summary: "다른 조건을 구분하기 전, 각 변수와 거래금액이 함께 어떻게 움직이는지 보여 줍니다.", points: ["상관계수 r은 두 변수가 직선에 가깝게 함께 움직이는 정도를 나타냅니다.", "다른 조건을 반영한 관계는 ‘부분회귀도’에서 확인해 주세요."], notes: ["상관관계만으로 원인과 결과를 판단할 수 없습니다."] },
  built_scatter_partial_v1: { summary: "다른 변수의 영향을 제거한 뒤, 선택한 변수와 금액 사이에 남은 관계를 보여 줍니다.", points: ["기울기는 해당 변수의 회귀계수와 같은 의미입니다.", "상관관계 산점도와 부호가 다르면 다른 조건의 영향을 함께 살펴봐 주세요."], notes: ["연속변수에 제공하며, 로그모형은 로그 척도에서 표시합니다. 인과관계를 뜻하지 않습니다."] },
  built_residual_diagnostics_v1: { summary: "어느 금액대와 거래 조건에서 오차가 큰지 확인합니다. 회귀계수에 영향을 크게 주는 거래도 함께 살펴볼 수 있습니다.", points: ["오차율이 음수이면 실제 금액보다 높게 추정한 경우입니다. 양수이면 낮게 추정한 경우입니다.", "금액대별 표는 오차의 크기와 퍼짐을, 조건별 표는 다른 거래와의 오차 차이를 보여 줍니다.", "주요 영향 거래는 단순 오차율이 아닌 회귀계수에 미치는 영향을 기준으로 선정합니다."], notes: ["분석에 사용한 표본 안의 진단입니다. 새로운 거래의 예측 성능은 CV-MAPE를 함께 확인해 주세요.", "집단별 차이가 특정 조건의 인과적 효과를 뜻하지는 않습니다."] },
  built_recommend_static_v1: { title: "Macro 모형 탐색", summary: "변수 조합과 모형을 비교해 분석 목적에 맞는 후보를 살펴봅니다. 탐색 결과가 기본회귀를 자동으로 바꾸지는 않습니다.", points: ["예측형은 CV-MAPE가 낮은 후보를 비교합니다. 검증 자료가 부족하면 대표모형으로 확정하지 않습니다.", "설명형은 로그 계열 모형을 AIC로 비교합니다. AIC는 적합도와 변수 수를 함께 고려하는 기준입니다.", "쌍둥이 확장은 유사한 지역의 거래를 보태기 전후의 결과를 비교합니다."], notes: ["탐색에 사용한 오차와 마지막 연도 확인 오차를 구분해 주세요. 후보를 고르는 데 사용한 오차는 낙관적일 수 있습니다.", "표본 수·실제 반영 변수·기준선과 선택 후보를 함께 확인해 주세요. 후보 순위가 개별 가격의 정확성을 보장하지는 않습니다."] },
  built_upper_scope_static_v1: { title: "상위지역 재적합 읽기", summary: "선택 지역의 상위 행정구역 거래에 별도로 적합한 결과입니다.", points: ["현재 지역과 상위지역의 표본 수·계수 방향·실제 반영 변수를 함께 확인해 주세요.", "기본회귀 때 계산한 결과를 펼쳐 보여 줍니다. 조건을 바꿨다면 통계분석을 다시 실행해 주세요."], notes: ["상위지역은 거래 구성이 다릅니다. 지표가 높다는 이유만으로 더 적합한 모형이라고 단정하지 마세요."] },
  built_model_selection_suggest_static_v1: { title: "추천 후보 읽기", summary: "설명력·예측오차·모형의 복잡도를 고려해 목적별 후보를 보여 줍니다.", points: ["설명형·균형형·예측형의 목적을 확인하고 후보를 선택해 주세요.", "실제 적용 변수와 표본, 사용된 오차 지표를 함께 비교해 주세요."], notes: ["추천은 정답이나 적정가격 판정이 아닙니다. 학습 오차와 검증 오차를 구분해 주세요."] },
  built_model_selection_compare_static_v1: { title: "모형 비교 읽기", summary: "변수 조합별 후보를 적합도와 오차 지표로 비교합니다.", points: ["AIC·BIC는 적합도와 모형의 복잡도를 함께 고려하며, 같은 비교 조건에서는 낮은 값을 선호합니다.", "MAPE와 CV-MAPE는 평가한 거래가 다르므로 같은 지표처럼 비교하지 마세요."], notes: ["지역·기간·표본·척도가 다른 후보는 수치만으로 우열을 판단하기 어렵습니다."] },
};

export function helpText(text: string): string {
  return text.replace(/\*\*/g, "")
    .replace(/나머지 대비/g, "오차율 차이").replace(/중위 오차/g, "오차 중앙값").replace(/오차 산포/g, "오차의 퍼짐")
    .replace(/\bscope\b/g, "분석 범위").replace(/\bin-sample\b/g, "학습 표본 안")
    .replace(/\bfold\b/g, "평가 구간").replace(/\bbaseline\b/g, "기준선")
    .replace(/\btime_adjust\b/g, "거래시점 보정").replace(/\bmodel_comparison\b/g, "모형 비교")
    .replace(/\bBest Subset\b/g, "변수 조합 비교").replace(/\bLocal\b/g, "현재 지역")
    .replace(/\bTwin1\b/g, "쌍둥이 확장 1").replace(/\bTwin2\b/g, "쌍둥이 확장 2");
}

export function builtHelpIntro(explain: AnalysisExplain) {
  return BUILT_HELP_INTROS[explain.spec_id];
}
