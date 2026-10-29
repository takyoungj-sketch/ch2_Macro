import type { AnalysisExplain } from "../types";

/** 회귀 실행 전·API explain 없을 때 */
export const BUILT_REGRESSION_HELP: AnalysisExplain = {
  spec_id: "built_regression_static_v1",
  spec_version: "1",
  title: "복합부동산 OLS 회귀",
  summary:
    "금액(또는 log 금액)에 대한 OLS 회귀. **탐색(통제 전) → 분석(통제 후) → 예측** 순으로 해석하세요.",
  formula: "금액 ~ 연면적·대지·연식·용도·도로 등",
  interpretation: [
    "학습 MAPE는 이 표본 안의 적합 오차입니다. CV-MAPE는 같은 식으로 과거 연도를 학습하고 다음 연도를 맞춘 오차이며, 모형 추천과 같은 계산입니다. 추천은 후보 전체의 숫자 결측을 한 번에 빼므로 행이 다르면 숫자가 달라집니다.",
    "산점도 탭으로 r과 β를 비교하세요.",
    "예측 패널은 변수 고정 후 한 점 예측.",
  ],
  limitations: ["인과·적정가격 아님", "표본·필터에 민감", "지분거래는 중위·회귀에서 기본 제외"],
  interpretation_hints: [],
  presets: [
    {
      id: "share_tx",
      question: "지분거래를 왜 분석에서 빼나요?",
      answer:
        "국토부 지분 행은 연면적(건물 전체)과 대지(지분)의 기준이 건마다 다를 수 있습니다. 목록에는 그대로 두고, ㎡당·회귀만 기본에서 뺍니다. 포함할지는 분석 패널에서 고릅니다. 토지 앱은 포함이 기본입니다.",
    },
  ],
};

export const BUILT_SCATTER_RAW_HELP: AnalysisExplain = {
  spec_id: "built_scatter_raw_v1",
  spec_version: "1",
  title: "상관관계 (통제 전)",
  summary: "원시 X vs 금액 산점도·Pearson r — **실제 시장 거래 분포** 탐색.",
  formula: "r = corr(X, 금액)",
  interpretation: [
    "다른 변수 영향이 섞여 있습니다.",
    "r과 β가 다르면 **부분회귀도** 탭으로 전환.",
  ],
  limitations: ["인과 해석 불가"],
  interpretation_hints: [],
  presets: [
    {
      id: "why_raw",
      question: "왜 통제 전도 필요한가요?",
      answer:
        "현장 데이터의 **실제 모양**을 먼저 봅니다. 통제 후만 보면 시장 분포 감각이 약해질 수 있어 둘 다 제공합니다.",
    },
  ],
};

export const BUILT_SCATTER_PARTIAL_HELP: AnalysisExplain = {
  spec_id: "built_scatter_partial_v1",
  spec_version: "1",
  title: "부분회귀도 (통제 후)",
  summary: "모형과 동일하게 다른 변수를 제거한 **잔차 vs 잔차**. 기울기 = 회귀 β.",
  formula: "Y잔차 vs X잔차 (Added Variable Plot)",
  interpretation: [
    "회귀 계수표와 **같은 의미**.",
    "파란 기울기선 = OLS β.",
    "부분 R² = 통제 후 추가 설명력 참고.",
  ],
  limitations: ["연속 변수만", "log 모형은 log 잔차 공간"],
  interpretation_hints: [],
  presets: [
    {
      id: "beta_line",
      question: "파란 기울기선은?",
      answer: "원점 기준 직선의 기울기가 **회귀 β**와 같습니다.",
    },
  ],
};

export const BUILT_RESIDUAL_HELP: AnalysisExplain = {
  spec_id: "built_residual_diagnostics_v1",
  spec_version: "1",
  title: "잔차 진단 읽기",
  summary:
    "금액대와 거래 조건에 따라 오차가 어떻게 달라지는지 확인합니다. 회귀계수에 영향을 크게 주는 거래도 함께 볼 수 있습니다.",
  formula: "오차% = (실제 − 예측) ÷ 실제 × 100",
  interpretation: [
    "오차율이 양수이면 실제 금액이 예측보다 높고, 음수이면 예측보다 낮습니다.",
    "예측은 화면 상단 MAPE와 **같은 방식**으로 계산합니다. log 모형이면 Duan 보정을 건 값입니다.",
    "집단별 **나머지 대비 (%p)**는 해당 집단 중위 오차율에서 그 집단을 제외한 나머지 거래의 중위 오차율을 뺀 값입니다.",
    "● 표시 = 그 집단 오차 분포가 나머지 표본과 다름(Mann–Whitney p<0.05). 표시가 없으면 n이 얇아 흔들린 것일 수 있으니 구조적 편향으로 읽지 마세요.",
    "집단별 차이는 거래 구성이나 모형에 포함되지 않은 조건과도 관련될 수 있습니다. 특정 변수의 인과적 효과로 해석하지 마세요.",
    "계약연도별 결과는 해당 연도의 표본 수와 거래 구성을 함께 확인해 주세요.",
  ],
  limitations: [
    "이 잔차 카드는 표본 안 오차입니다. 과거 연도 밖의 오차는 위 회귀 카드의 CV-MAPE를 참고하세요. 완료한 평가 연도·실패 사유를 함께 확인하며 미래 정확도를 보증하지 않습니다.",
    "오차율은 실제 거래금액이 작을 때 크게 벌어질 수 있습니다. 예측금액이 양수라면 오차율은 +100% 미만이지만 음수 방향에는 같은 제한이 없습니다. 음수 중위 오차는 학습 거래의 절반 이상에서 예측금액이 실제보다 높다는 뜻이며, 새로운 거래의 오차 방향을 보증하지 않습니다.",
    "10건 미만 집단은 표에 넣지 않습니다.",
    "분석 초점 모형에만 붙습니다. 상위지역 재적합에는 없습니다.",
  ],
  interpretation_hints: [],
  presets: [
    {
      id: "excess_bias",
      question: "«나머지 대비»와 «중위 오차»는 왜 다른가요?",
      answer:
        "중위 오차는 그 집단의 치우침이고, 나머지 대비는 거기서 **나머지 표본의 치우침을 뺀** 값입니다. 표본 전체가 −6% 치우쳐 있는데 어떤 집단도 −6%면 그 집단은 특별하지 않습니다. 진단에서 의미 있는 건 차이 쪽입니다.",
    },
    {
      id: "influential",
      question: "주요 영향 거래는 어떻게 고르나요?",
      answer:
        "Cook 거리가 큰 거래부터 표시합니다. 단순 오차율과 달리 회귀계수에 미치는 영향을 나타냅니다. 계수 변화 표에서는 기존 재적합 결과를 확인할 수 있습니다. 영향도가 크다는 이유만으로 오류 거래나 제외 대상으로 판단하지 마세요.",
    },
    {
      id: "spread",
      question: "«오차 산포»가 분위마다 다르면?",
      answer:
        "해당 금액대에서 거래별 오차가 더 넓게 퍼져 있다는 뜻입니다. 오차율 표준편차와 표본 수를 함께 확인해 주세요. 이분산성 검정 결과만으로 특정 거래의 오차나 미래 정확도를 단정할 수는 없습니다.",
    },
  ],
};

export const BUILT_PREDICTION_HELP: AnalysisExplain = {
  spec_id: "built_prediction_static_v1",
  spec_version: "2",
  title: "복합부동산 회귀 예측",
  summary:
    "나머지 변수를 고정한 **한 점 OLS 통계적 추정**. 평균 추정범위(CI)·개별 거래 예측범위(PI)는 모형의 불확실성 참고입니다.",
  formula: "ŷ = Xβ",
  interpretation: [
    "통계적 추정값: 선택한 거래자료와 회귀모형의 중심값입니다. AVM·감정평가액이 아닙니다.",
    "95% 평균 추정범위: 이 조건에서 평균적인 가격수준.",
    "95% 개별 거래 예측범위: 개별 거래 변동까지 포함한 통계적 범위.",
    "n이 작으면 범위가 넓습니다.",
  ],
  limitations: ["적정가·감정 아님", "학습 범위 밖 입력은 외삽", "범위는 가액을 보증하지 않음"],
  interpretation_hints: [],
  presets: [
    {
      id: "pi",
      question: "평균 추정범위와 개별 거래 예측범위 차이는?",
      answer:
        "평균 추정범위(CI)는 **평균 가격수준**의 불확실성입니다. 개별 거래 예측범위(PI)는 **개별 거래 변동**을 포함해 더 넓습니다. 실제 대상물건이 반드시 그 안에 있다는 뜻이 아닙니다.",
    },
  ],
};

export const BUILT_MODEL_SELECTION_SUGGEST_HELP: AnalysisExplain = {
  spec_id: "built_model_selection_suggest_static_v1",
  spec_version: "2",
  title: "추천 후보 (Pareto)",
  summary:
    "후보 블록 조합에서 **설명형·균형형·예측형** 3후보를 제시합니다. 「최적」·「정답」이 아니라 **목적별 추천** — 채택은 사용자.",
  formula: "Best Subset pool → Adj R² 1위 · MAPE 1위 · 균형 점수 1위 (vs 현재 baseline)",
  interpretation: [
    "설명형 — Adj R²(log) 우선 · 보고서·요인 해석.",
    "예측형 — 금액 MAPE 우선 · 예측·오차 최소화.",
    "균형형 — Adj R²·MAPE·AIC·변수 수 trade-off.",
    "추천 신뢰도 + reasons — MAPE만으로 추천된 것이 아님을 표시.",
    "Forward 제외 사유 — 참고용 (AIC greedy).",
  ],
  limitations: ["적정가·최적 회귀식 아님", "in-sample MAPE · CV 아님", "n<30 주의"],
  interpretation_hints: [],
  presets: [
    {
      id: "vs_compare",
      question: "추천과 모형 비교 차이는?",
      answer:
        "추천=목적별 3후보 + baseline 대비 trade-off. 모형 비교=AIC/BIC/MAPE 탭별 상위 k — 전체 조합 탐색.",
    },
    {
      id: "purpose",
      question: "어떤 후보를 쓰면 되나요?",
      answer:
        "가격 예측 → 예측형 · 보고서 설명 → 설명형 · 둘 다 → 균형형. AI에게 목적을 말하면 차이를 설명합니다.",
    },
  ],
};

export const BUILT_MODEL_SELECTION_COMPARE_HELP: AnalysisExplain = {
  spec_id: "built_model_selection_compare_static_v1",
  spec_version: "1",
  title: "모형 비교 (Group Best Subset)",
  summary: "후보 블록 부분집합을 평가해 **AIC·BIC·MAPE** 탭별 상위 후보 — 사용자 채택.",
  formula: "2^k−1 subset OLS · subset당 linear/log/log-log 중 원척도 CV-MAPE 최소 (설명형 AIC는 log 가족만)",
  interpretation: [
    "기준별 1위가 다를 수 있음 — 정답 아님.",
    "카드에서 model_comparison 확인.",
    "이 모형으로 분석 → /regression/run.",
  ],
  limitations: ["≤128 subset", "표본·필터에 민감"],
  interpretation_hints: [],
  presets: [
    {
      id: "aic_bic",
      question: "AIC와 BIC 차이는?",
      answer: "AIC=2k 페널티, BIC=k·ln(n) — BIC가 더 단순한 모형 선호.",
    },
  ],
};

export const BUILT_RECOMMEND_HELP: AnalysisExplain = {
  spec_id: "built_recommend_static_v1",
  spec_version: "12",
  title: "Macro 모형 탐색",
  summary:
    "예측형·설명형·쌍둥이 확장 탭으로 나눕니다. 예측형은 CV-MAPE로 탐색 1위를 고르고, 검증이 얇으면 대표모형으로 확정하지 않습니다. 설명형은 log 계열 AIC 1위입니다. 쌍둥이 확장은 그 탐색 1위를 출발점으로 Local·Twin1·Twin2를 봅니다. 기본 통계 식은 바꾸지 않습니다.",
  interpretation: [
    "①의 순위는 CV-MAPE가 낮은 순입니다. 최저보다 1.0%p 이내이고 실제 평가 거래·분할·계산 기준의 일치가 확인되면 성능 유사로 묶습니다. 같은 표본 수만으로 판정하지 않습니다. 이 폭은 화면 규칙이며 통계적 동률이 아닙니다. 그 안에서 대지면적(계수 양)이나 연식(계수 음)만 더한 식이 p<0.1이면 해석 후보로 따로 보여 줍니다. 순위를 누르면 그 식과 계수를 보고, 값 계산은 그 식만 다시 적합합니다. Local 기준선과 Twin은 예측 최소 식입니다. AIC 설명형은 이 해석 후보와 별개입니다.",
    "마지막 연도는 후보를 고르는 데 일절 쓰지 않고 떼어 둡니다. ①의 CV-MAPE는 그 앞의 연도들만으로 낸 값이고, 「마지막 연도로 확인」은 고르는 데 쓰지 않은 그 해로만 잰 값입니다. 그래도 ①은 수백 개 후보 중 최소값이라 여전히 낙관적이므로, 두 값이 크게 벌어지면 그 식은 이 지역에서 덜 안정적입니다.",
    "CV-MAPE는 과거 연도로 학습해 다음 연도를 맞혀 본 오차이며, fold 평균이 아니라 거래 가중 평균입니다. 거래가 많은 연도가 지표를 더 끌어당깁니다.",
    "예측을 자르지 않은 값이라, 크게 틀린 예측이 있으면 오차에 그대로 들어갑니다. 예측을 잘라 내면 크게 실패한 식이 덜 실패한 것처럼 보이기 때문입니다. 대신 「범위 밖 예측」 비율을 따로 보여 주는데, 이는 성능이 아니라 그 식의 예측이 얼마나 튀는지를 나타냅니다.",
    "「중위 오차」가 CV-MAPE보다 훨씬 낮으면 평균을 몇몇 거래가 끌고 있다는 뜻입니다. 그때는 대다수 거래에서의 오차는 중위값에 가깝습니다. 다만 식을 고르는 기준은 평균으로 둡니다. 중위로 고르면 대다수 거래는 잘 맞히지만 크게 틀리는 거래가 많은 식이 1위가 될 수 있고, 정작 설명이 필요한 쪽은 그 크게 틀린 거래입니다.",
    "만족도 등급은 두 CV 중 나쁜 쪽으로 냅니다. 마지막 연도가 더 좋게 나와도 등급을 올려 주지 않는데, 그 해 하나만으로 잰 값이라 그 해가 쉬웠을 뿐일 수 있기 때문입니다.",
    "거래시점은 보정하지 않습니다. 조회 기간(기본 5년)의 거래를 함께 넣어 적합하므로, 값 계산 결과는 특정 연도의 시세가 아니라 그 기간의 명목 가격 수준입니다. 최근 시세만 보려면 조회 연도를 좁히세요.",
    "표본 게이트는 적합 표본 10건, 지역 표본 15건, 신뢰 권장 30건입니다. 유효 값이 10건 미만인 변수 블록은 탐색 풀에서 빠지고 ①의 경고에 이유가 적힙니다.",
    "②는 기본 통계 회귀실험과 같은 골격입니다. 식·계수·적합 표본·CV-MAPE를 여기서 읽습니다. Twin 실험1을 눌러도 이 Local 식은 바뀌지 않습니다.",
    "척도는 선형·log(금액)·log-log를 같은 표본에서 비교합니다. log-log는 면적 블록이 있을 때만, 면적만 log입니다.",
    "③ Twin1은 Local 식·척도를 유지한 채 쌍둥이 1위 거래만 보태고, Local에 지역 더미가 있었든 없었든 지역 더미를 넣습니다. 예측오차와 주요 계수 방향을 같이 보고 적용 여부를 판단합니다. Local 식은 ②에 그대로 남습니다.",
    "Twin1 예측은 채택과 별개입니다. CV가 나아지지 않아도 1위 표본 + 지역 더미로 다시 적합한 값·범위를 ③에서 봅니다.",
    "④ Twin 실험2는 Local + Twin 1위 표본에서 예측형(선형·log·log-log, CV-MAPE) 식을 다시 고르는 확장 재탐색입니다. 선정용 오차이며 독립 확인 결과가 아닙니다. 설명형 AIC는 쓰지 않으며 기본 통계 식은 바꾸지 않습니다.",
    "판단 순서는 예측력 → 계수 안정 → 표본입니다. n만으로 채택하지 않고, Twin 후보는 거래가격이 아니라 구성·체급으로 고릅니다.",
    "⑤는 Local · Twin1(식 고정) · Twin2(재탐색) 숫자를 나란히 봅니다. Twin2는 확장 재탐색이며 Twin이 이겨도 기본 통계 식을 덮지 않습니다.",
    "이 창은 왼쪽 변수와 척도를 바꾸지 않습니다. ⑤의 기본 회귀실험은 사용자가 실행한 식을 그대로 둡니다. 30건 미만이거나 계수당 5건 미만이면 식 아래에 참고용 문장을 붙입니다.",
    "값 계산은 ②(Local), ③ Twin1 재적합, ④ Twin 실험2에서 각각 열 수 있습니다. 통계적 추정값이며 개별 적정가·AVM이 아닙니다.",
  ],
  limitations: ["적정가·투자 판단 아님", "통계적 추정이며 현장 판단을 대체하지 않음"],
  interpretation_hints: [],
  presets: [
    {
      id: "ai_diagnosis",
      question: "AI 진단을 요약해 주세요.",
      answer: "",
    },
    {
      id: "why_error_intensity",
      question: "예측 오차는 어떻게 읽나요?",
      answer: "",
    },
  ],
};

export { BUILT_VAR_SELECT_HELP, BUILT_RESPONSE_SCALE_HELP, BUILT_SAMPLE_HELP } from "./builtRegressionSettingsCopy";

export const BUILT_UPPER_SCOPE_HELP: AnalysisExplain = {
  spec_id: "built_upper_scope_static_v1",
  spec_version: "1",
  title: "상위 scope 비교",
  summary:
    "분석 초점(예: 읍면동)과 직계 상위(시군구·시도 등)에서 **같은 변수·모형**으로 회귀한 결과를 나란히 봅니다.",
  interpretation: [
    "상위는 표본이 커져 계수가 안정될 수 있으나, 지역 이질성이 섞입니다.",
    "초점과 상위 계수 부호·크기가 다르면 해상도·구성 차이를 의심하세요.",
  ],
  limitations: ["동일 시장이 아님", "인과·적정가 아님"],
  interpretation_hints: [],
  presets: [
    {
      id: "when",
      question: "언제 보나요?",
      answer: "초점 n이 작거나 계수 불안정할 때, 상위 패턴이 같은 방향인지 참고합니다.",
    },
  ],
};
