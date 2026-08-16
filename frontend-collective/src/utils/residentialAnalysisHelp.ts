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

/** API 응답 전·오류 시 — 집합상가·공장 cluster 효용지수 (주거와 동일 spec) */
export const CLUSTER_FLOOR_INDEX_HELP: AnalysisExplain = {
  ...RESIDENTIAL_FLOOR_INDEX_HELP,
  spec_id: "cluster_floor_index_regression_static_v1",
  title: "회귀 기반 층·면적 효용지수 (도로 cluster)",
  summary:
    "도로 cluster 거래에 반로그 OLS(HC3)를 적용해, 기준 구간=100% 상대 ㎡당 단가 지수(%)를 산출합니다. " +
    "회귀 omitted category=거래 최다 층·구간, 화면(층 탭)=1층=100% 환산. 회귀 탭과 spec·수치가 다릅니다.",
  formula:
    "ln(㎡당단가) = β₀ + ln(연면적, 면적형 탭 제외) + 연식 + 거래시점(반기) 더미 + Σ γ_g·D_g · HC3 강건표준오차",
  reference: "층=1층(화면), 회귀=거래 최다 층 · 면적형=중앙값 구간",
  floor_groups: [
    "1층 → 화면 지수 100% (표시 기준, 거래 없으면 —)",
    "회귀 omitted category → 거래 최다 층·구간 (표본 n≥5)",
    "층 탭: 상대(1·저·중·고·최상) / 개별층 더미 / 절대구간(1–5·6–15·16+) 선택 가능",
    "저층부 → cluster 내 max층 대비 하위 30% (1·최상층 제외)",
    "중층부 → max층 대비 30~70%",
    "고층부 → max층 대비 70% 초과 (최상층 제외)",
    "최상층 → cluster 내 최고층",
  ],
  controls: ["ln(연면적, 면적형 탭 제외)", "연식", "거래시점(반기)"],
  interpretation: [
    "지수는 「비슷한 연면적·연식·거래시점」 조건에서의 층·면적형 간 상대 수준입니다.",
    "100%보다 낮을수록 기준 대비 ㎡당 단가가 낮은 패턴입니다.",
    "95% CI는 HC3 강건표준오차 기반 구간 추정치입니다.",
  ],
  limitations: [
    "도로 cluster·분석 기간 내 패턴 — 인과 추론 불가",
    "동일 도로 내 건물·max층·입지 차이 잔존",
    "구간별 n<5 → 해당 더미·지수 미산출",
    "셀 n<15 → 참고용 표시",
    "회귀 분석 탭(금액 OLS)과 수치가 일치하지 않음",
  ],
};

/** 회귀 실행 전에도 표시할 주거 회귀 기본 도움말 */
export const RESIDENTIAL_REGRESSION_HELP: AnalysisExplain = {
  spec_id: "residential_regression_explore_static_v1",
  spec_version: "1",
  title: "단지 가격 형성 분석 (탐색용)",
  summary:
    "선택한 표본·변수에서 가격이 어떻게 형성되는지 읽기 위한 OLS입니다. AVM·적정가가 아닙니다. " +
    "기본은 선형(만원), 로그는 % 변화 옵션. 효용지수 탭의 ln(㎡당) 반로그 지수와는 별도 spec입니다.",
  formula: "금액(만원) = β₀ + Σ β_k·X_k  (선형 OLS · 기본)",
  reference: "범주형 변수는 drop_first 기준 범주 대비",
  floor_groups: [
    "relative: 1·최상·저·중·고 (단지 max층 대비)",
    "dummy: 개별 층 더미",
    "grouped: 1–5 / 6–15 / 16+",
    "linear: 층 선형",
  ],
  controls: ["전용면적", "연식", "층", "동(아파트·연립)", "권리(분양권)"],
  interpretation: [
    "기본(선형): 연속 변수 1단위 증가 시 금액(만원) 변화, 더미는 기준 범주 대비 만원 차이.",
    "로그 옵션: 연속 변수는 대략 % 변화 — 회귀 결과 「쉬운 설명」 참고.",
    "시나리오 계산은 참고값이며 AVM·적정가가 아닙니다.",
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

/** 비주거(도로 cluster) 회귀 — API explain 없을 때 */
export const COMMERCIAL_REGRESSION_HELP: AnalysisExplain = {
  ...RESIDENTIAL_REGRESSION_HELP,
  spec_id: "commercial_regression_explore_static_v1",
  title: "도로 cluster 가격 형성 분석 (탐색용)",
  summary:
    "선택한 도로 cluster 표본·변수에서 가격이 어떻게 형성되는지 읽기 위한 OLS입니다. AVM·적정가가 아닙니다. " +
    "분석 단위는 건물(단지)이 아니라 도로명 cluster입니다.",
  formula: "금액(만원) = β₀ + Σ β_k·X_k  (선형 OLS · 기본)",
  controls: ["연면적", "연식", "층", "용도지역", "건축물용도", "도로폭"],
  limitations: [
    "도로 cluster 내 표본 — 건물 단위 해석과 다름",
    "변수·필터에 따라 결과 변경",
    "외삽·인과·투자 판단용 아님",
  ],
};

export const COLLECTIVE_TREND_HELP: AnalysisExplain = {
  spec_id: "collective.trend.v1",
  spec_version: "1.0",
  title: "단기 추세 (롤링)",
  summary:
    "as_of 기준 최근 구간을 롤링 버킷으로 묶어 거래량·단가(또는 금액) 추세를 봅니다. 연도 from/to와 별개로 모달 기본 추세입니다.",
  interpretation: [
    "버킷별 건수와 대표 단가(또는 금액)를 함께 봅니다.",
    "표본이 적은 구간은 변동이 클 수 있습니다.",
  ],
  limitations: ["단기 패턴 — 장기 추세 탭과 다름", "단지·cluster·기간에 종속"],
  interpretation_hints: [],
  presets: [],
  controls: [],
  floor_groups: [],
};

export const COLLECTIVE_LONG_TERM_HELP: AnalysisExplain = {
  spec_id: "collective.long_term.v1",
  spec_version: "1.0",
  title: "장기 추세 (연도)",
  summary: "달력 연도별 집계로 2010년대~ 장기 흐름을 봅니다. 단기 롤링 추세와 축이 다릅니다.",
  interpretation: [
    "연도별 건수·단가 수준을 비교합니다.",
    "행정·단지명·데이터 품질 변화로 단절이 있을 수 있습니다.",
  ],
  limitations: ["연도 필터와 무관하게 표시되는 경우가 있음", "과거 원장 품질 한계"],
  interpretation_hints: [],
  presets: [],
  controls: [],
  floor_groups: [],
};

export const COLLECTIVE_HISTOGRAM_HELP: AnalysisExplain = {
  spec_id: "collective.histogram.v1",
  spec_version: "1.0",
  title: "분포 (히스토그램)",
  summary: "선택 기간·필터 안 거래의 단가(또는 금액) 분포를 봅니다.",
  interpretation: ["봉우리·꼬리·이상치를 눈으로 확인합니다.", "회귀 전에 분포 왜도를 가늠할 때 유용합니다."],
  limitations: ["구간 폭·표본에 따라 모양이 달라집니다."],
  interpretation_hints: [],
  presets: [],
  controls: [],
  floor_groups: [],
};

export const COLLECTIVE_TX_LIST_HELP: AnalysisExplain = {
  spec_id: "collective.tx_list.v1",
  spec_version: "1.0",
  title: "거래 목록",
  summary: "화면에 집계된 표본의 개별 거래 행입니다. 통계·회귀와 같은 정제 규칙을 따릅니다.",
  interpretation: ["계약일·면적·층·금액 등으로 이상·특수 거래를 확인합니다."],
  limitations: ["마스킹 번지·신고 오류가 있을 수 있습니다."],
  interpretation_hints: [],
  presets: [],
  controls: [],
  floor_groups: [],
};

/** 모달 탭 id → 페이지 설명 */
export const SALE_RENT_JOIN_HELP: AnalysisExplain = {
  spec_id: "sale_rent_join_v1",
  spec_version: "1",
  title: "매매 건물 × 전월세 조인",
  summary:
    "같은 building_key가 임대 원장에도 있을 때만 전세·반전세·월세 원값과 적용 전환율·환산을 보여 줍니다. 원장·목록은 합치지 않습니다.",
  formula: "정확 키 = 유형|시|시군구|읍면동|name:단지명 해시. 보조 층 없음.",
  interpretation: [
    "조인 없음 = 키가 다르거나 임대 거래가 없음.",
    "환산 P50은 비교용입니다. 그 건물 시세·수익률이 아닙니다.",
    "창은 매매와 같은 3·5·7년입니다.",
  ],
  limitations: [
    "단독·분양권·비주거 집합·복합은 대상 아님",
    "시군구 전환율 fallback이면 그 건물 고유 r이 아님",
  ],
  interpretation_hints: [],
  presets: [],
  controls: [],
  floor_groups: [],
};

export function collectiveModalPanelHelp(
  panel: string,
): AnalysisExplain | null {
  switch (panel) {
    case "trend":
      return COLLECTIVE_TREND_HELP;
    case "long_term":
      return COLLECTIVE_LONG_TERM_HELP;
    case "histogram":
      return COLLECTIVE_HISTOGRAM_HELP;
    case "transactions":
      return COLLECTIVE_TX_LIST_HELP;
    case "regression":
      return RESIDENTIAL_REGRESSION_HELP;
    case "floor_index":
      return RESIDENTIAL_FLOOR_INDEX_HELP;
    case "rent":
      return SALE_RENT_JOIN_HELP;
    default:
      return null;
  }
}

export function commercialModalPanelHelp(panel: string): AnalysisExplain | null {
  switch (panel) {
    case "trend":
      return COLLECTIVE_TREND_HELP;
    case "long_term":
      return COLLECTIVE_LONG_TERM_HELP;
    case "histogram":
      return COLLECTIVE_HISTOGRAM_HELP;
    case "transactions":
      return COLLECTIVE_TX_LIST_HELP;
    case "regression":
      return COMMERCIAL_REGRESSION_HELP;
    case "floor_index":
      return CLUSTER_FLOOR_INDEX_HELP;
    default:
      return null;
  }
}
