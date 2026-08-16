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
  limitations: ["인과·적정가격 아님", "표본·필터에 민감"],
  interpretation_hints: [],
  presets: [],
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
  spec_version: "1",
  title: "복합부동산 회귀 예측",
  summary: "나머지 변수를 고정한 **한 점 OLS 예측**. PI·CI는 불확실성 참고.",
  formula: "ŷ = Xβ",
  interpretation: [
    "PI: 개별 거래 1건 예측 범위.",
    "CI: 평균 예측 불확실성.",
    "n이 작으면 PI가 넓습니다.",
  ],
  limitations: ["적정가·감정 아님", "학습 범위 밖 입력은 외삽"],
  interpretation_hints: [],
  presets: [
    {
      id: "pi",
      question: "PI와 CI 차이는?",
      answer: "PI는 **개별 거래** 변동 포함, CI는 **평균 예측값** 불확실성만 반영합니다.",
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
  formula: "2^k−1 subset OLS · subset당 linear/log 중 AIC 최소",
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
  spec_version: "1",
  title: "모형 탐색 · 판정",
  summary:
    "SSOT 변수 풀에서 Local 탐색 → (선택) Twin pool → **판정·권장 행동**. 예측 채택은 사용자 판단.",
  interpretation: [
    "CV-MAPE 적합 등급은 예측 목적 참고.",
    "예측 부적합이어도 설명형·비교사례·용도×지목 통계는 활용 가능.",
    "AI Assistant는 표본·Twin·변수 한계를 Facts 기준으로 해석.",
  ],
  limitations: ["적정가·투자 판단 아님", "권장 행동은 통계적 적합성 보조"],
  interpretation_hints: [],
  presets: [
    {
      id: "ai_diagnosis",
      question: "AI 진단을 요약해 주세요.",
      answer: "",
    },
    {
      id: "why_unsuitable",
      question: "왜 예측이 부적합한가요?",
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
