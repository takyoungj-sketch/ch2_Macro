import type { AnalysisExplain } from "../types";

/** API 응답 전·오류 시에도 표시할 주거 효용지수 기본 도움말 */
export const RESIDENTIAL_FLOOR_INDEX_HELP: AnalysisExplain = {
  spec_id: "residential_floor_index_regression_static_v1",
  spec_version: "1",
  title: "회귀 기반 층·동·면적·권리 효용지수",
  summary:
    "단지(또는 코호트) 거래에 반로그 OLS를 적용해, 기준 구간=100% 상대 ㎡당 단가 지수(%)를 산출합니다. " +
    "회귀 분석 탭(금액 OLS)과 spec·수치가 다릅니다.",
  formula:
    "ln(㎡당단가) = β₀ + ln(전용면적, 면적형 탭 제외) + 연식 + 거래시점(반기) 더미 + (동·면적·권리 탭 시 상대층 통제) + (코호트 시 단지 FE) + Σ γ_g·D_g · HC3 강건표준오차",
  index_rule:
    "회귀 omitted category = 거래 최다 층 구간. 화면(층 탭) 지수는 1층=100% 기준.",
  reference: "층=1층(화면), 회귀=거래 최다 층 · 동·권리=거래 최다 구간, 면적형=중앙값 구간",
  floor_groups: [
    "1층 → 화면 지수 100% (표시 기준, 거래 없으면 —)",
    "회귀 omitted category → 거래 최다 층·구간 (표본 n≥5)",
    "층 탭: 상대(1·저·중·고·최상) / 개별층 더미 / 절대구간(1–5·6–15·16+) 선택 가능",
    "저층부 → 단지 max층 대비 하위 30% (1·최상층 제외)",
    "중층부 → max층 대비 30~70%",
    "고층부 → max층 대비 70% 초과 (최상층 제외)",
    "최상층 → 단지 최고층",
  ],
  controls: ["ln(전용면적, 면적형 탭 제외)", "연식", "거래시점(반기)", "상대 층구간(비층 탭)", "단지 고정효과(코호트)"],
  interpretation: [
    "지수는 「비슷한 전용면적·연식·거래시점」 조건에서의 층·동·면적·권리 간 상대 수준입니다.",
    "100%보다 낮을수록 기준 대비 ㎡당 단가가 낮은 패턴입니다.",
    "95% CI는 HC3 강건표준오차 기반 구간 추정치입니다.",
  ],
  limitations: [
    "단지·분석 기간 내 패턴 — 인과 추론 불가",
    "구간별 n<5 → 해당 더미·지수 미산출",
    "셀 n<15 → 참고용 표시",
    "회귀 분석 탭(금액 OLS)과 수치가 일치하지 않음",
  ],
  interpretation_hints: [],
  presets: [
    {
      id: "vs_regression",
      question: "회귀 분석 탭과 무엇이 다른가요?",
      answer:
        "효용지수는 ln(㎡당단가) 반로그로 한 차원의 상대 지수(%)만 고정 spec으로 산출합니다. " +
        "회귀 탭은 금액(만원) 수준 OLS로 변수·층 형식을 바꿀 수 있는 탐색용입니다.",
    },
    {
      id: "interpret",
      question: "지수를 어떻게 해석하나요?",
      answer:
        "기준 구간 100%. 예: 고층부 112% → 통제 조건에서 기준 대비 ㎡당 단가가 약 12% 높은 패턴(반로그).",
    },
  ],
};

/** 회귀 실행 전에도 표시할 주거 회귀 기본 도움말 */
export const RESIDENTIAL_REGRESSION_HELP: AnalysisExplain = {
  spec_id: "residential_regression_explore_static_v1",
  spec_version: "1",
  title: "단지 회귀 분석 (탐색용)",
  summary:
    "선택한 변수로 거래금액(만원) OLS를 추정합니다. 변수·층 형식을 바꿀 수 있는 탐색용이며, " +
    "효용지수 탭의 ln(㎡당) 반로그 지수와는 별도 spec입니다.",
  formula: "금액(만원) = β₀ + Σ β_k·X_k  (OLS, 수준 모델)",
  reference: "범주형 변수는 drop_first 기준 범주 대비",
  floor_groups: [
    "relative: 1·최상·저·중·고 (단지 max층 대비)",
    "dummy: 개별 층 더미",
    "grouped: 1–5 / 6–15 / 16+",
    "linear: 층 선형",
  ],
  controls: ["전용면적", "연식", "층", "동(아파트·연립)", "권리(분양권)"],
  interpretation: [
    "연속 변수: 1단위 증가 시 금액(만원) 변화.",
    "더미: 기준 범주 대비 금액 차이(만원).",
    "예측: 적합 후 입력 조건의 금액·95% 구간 추정.",
  ],
  limitations: [
    "변수·층 형식 선택에 따라 결과 변경",
    "효용지수 탭과 수치 불일치가 정상",
    "단지·기간 내 표본 — 외삽·인과·투자 판단용 아님",
  ],
  interpretation_hints: [],
  presets: [
    {
      id: "vs_floor_index",
      question: "효용지수 탭과 무엇이 다른가요?",
      answer:
        "회귀 탭은 금액(만원) OLS, 효용지수 탭은 ln(㎡당단가) 반로그로 한 차원의 상대 지수(%)만 산출합니다.",
    },
  ],
};
