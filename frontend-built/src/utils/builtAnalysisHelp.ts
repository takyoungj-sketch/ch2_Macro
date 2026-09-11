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
    "Adj R²·계수·VIF는 scope 내 **통계적 패턴** 참고.",
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
  spec_version: "7",
  title: "Macro 모형 탐색",
  summary:
    "① CV-MAPE로 대표 예측모형을 고르고 → ② 그 식을 이 지역 거래의 Local 기준선으로 두고 → ③ 같은 식에 유사 지역 거래를 보태 예측력이 나아지는지 보며 → ④ Local · Twin1 · Twin2 숫자를 나란히 봅니다. 기본 통계 식은 바꾸지 않습니다.",
  interpretation: [
    "①은 왜 이 식인가만 답합니다. 순위 표에는 CV-MAPE만 둡니다.",
    "②는 기본 통계 회귀실험과 같은 골격입니다. 식·계수·적합 표본·CV-MAPE를 여기서 읽습니다.",
    "척도는 선형·log(금액)·log-log를 같은 표본에서 비교합니다. log-log는 면적 블록이 있을 때만, 면적만 log입니다.",
    "③ Twin1은 Local 식·척도를 유지한 채 쌍둥이 1위 거래만 보태고, Local에 지역 더미가 있었든 없었든 지역 더미를 넣습니다. 예측오차와 주요 계수 방향을 같이 보고 적용 여부를 판단합니다. Local 식은 ②에 그대로 남습니다.",
    "Twin1 예측은 채택과 별개입니다. CV가 나아지지 않아도 1위 표본 + 지역 더미로 다시 적합한 값·범위를 ③에서 봅니다.",
    "Twin 실험2는 Local + Twin 1위 표본에서 예측형(선형·log·log-log, CV-MAPE) 식을 다시 고르는 출시 전 확인용입니다. 설명형 AIC는 쓰지 않으며 기본 통계 식은 바꾸지 않습니다.",
    "판단 순서는 예측력 → 계수 안정 → 표본입니다. n만으로 채택하지 않고, Twin 후보는 거래가격이 아니라 구성·체급으로 고릅니다.",
    "④는 Local · Twin1(식 고정) · Twin2(재탐색) 숫자를 나란히 봅니다. Twin2는 확인용이며 기본 통계 식은 바꾸지 않습니다.",
    "값 계산은 ②(Local), ③ Twin1 재적합, Twin 실험2에서 각각 볼 수 있습니다. 통계적 추정값이며 개별 적정가·AVM이 아닙니다.",
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
