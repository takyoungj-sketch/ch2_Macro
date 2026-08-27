import type { AnalysisExplain } from "../types";

/** API 응답 전·오류 시에도 표시할 주거 효용지수 기본 도움말 */
export const RESIDENTIAL_FLOOR_INDEX_HELP: AnalysisExplain = {
  spec_id: "residential_floor_index_regression_static_v2",
  spec_version: "2",
  title: "층·동·면적 효용지수 — 이렇게 계산합니다",
  summary:
    "같은 단지(또는 코호트) 실거래의 ln(㎡당단가)를 회귀합니다. 전용면적·연식·거래시점(반기)을 맞춘 뒤, 층·동·면적형·권리 한 차원만 상대 %로 봅니다. 회귀 분석 탭(금액 OLS)과 spec·숫자가 다릅니다.",
  formula:
    "ln(㎡당단가) = β₀ + ln(전용면적, 면적형 탭 제외) + 연식 + 거래시점(반기) + (비층 탭이면 상대층) + (코호트면 단지 FE) + Σ γ_g·D_g · HC3",
  index_rule:
    "지수 = exp(γ)×100. 회귀 기준=거래 최다 구간. 층 탭 화면은 1층=100%로 환산. 면적형 기준=전용면적 중앙값 칸.",
  reference: "층=1층(화면) · 면적형=중앙값 구간 · 동·권리=거래 최다 구간",
  floor_groups: [
    "층별(기본): 단지 최고층 대비 1층 · 저층부(30% 이하) · 중층부(30~70%) · 고층부(70% 초과) · 최상층. 개별 층·절대 구간(1–5/6–15/16+)으로 바꿀 수 있습니다.",
    "면적별: 전용면적 30㎡ 반올림. 예 84㎡ → 90㎡. 기준은 표본 중앙값 칸. ln(전용면적)은 이 탭에서 빼 이중 반영을 막습니다.",
    "동별: 거래 최다 동=100. 권리별(분양권): 거래 최다 권리=100.",
  ],
  controls: ["ln(전용면적, 면적형 탭 제외)", "연식", "거래시점(반기)", "상대 층(비층 탭)", "단지 고정효과(코호트)"],
  interpretation: [
    "표의 평균은 칸 원자료, 지수는 면적·연식·시점을 맞춘 상대 %입니다. 둘이 어긋날 수 있습니다.",
    "112%면 기준보다 ㎡당 단가가 약 12% 높은 패턴입니다.",
    "칸 n<15는 참고용, 구간 n<5는 지수를 안 냅니다.",
  ],
  limitations: [
    "단지·기간 안 패턴 — 인과·적정가 아님",
    "회귀 분석 탭과 숫자 불일치는 정상",
    "전체 n<50이면 이 탭을 막습니다(실험 모드 제외)",
  ],
  interpretation_hints: [],
  presets: [
    {
      id: "how_floor",
      question: "층별 지수는 어떻게 나오나요?",
      answer:
        "단지 실거래 ln(㎡당단가) 회귀입니다. 기본은 최고층 대비 상대 구간입니다. 전용면적·연식·반기를 맞춘 뒤 층 더미 계수 γ를 exp(γ)×100으로 바꿉니다. 화면은 1층=100입니다. 평균 열은 원자료라 지수와 다를 수 있습니다.",
    },
    {
      id: "how_area",
      question: "면적별 지수는 어떻게 나오나요?",
      answer:
        "전용면적을 30㎡로 반올림한 면적형입니다. 기준은 표본 중앙값 칸=100. 면적은 구간 더미로만 넣고 ln(전용면적)은 뺍니다. 층·연식·시점은 통제합니다.",
    },
    {
      id: "mean_vs_index",
      question: "평균과 지수가 다른 이유는요?",
      answer:
        "평균은 통제 없는 칸 평균입니다. 지수는 비슷한 면적·연식·시점을 맞춘 상대 %입니다. 고층이 최근 상승기에 몰리면 평균은 높아도 지수는 낮을 수 있습니다.",
    },
    {
      id: "vs_regression",
      question: "회귀 분석 탭과 무엇이 다른가요?",
      answer:
        "효용지수는 ln(㎡당) 반로그로 한 차원의 상대 지수만 고정 spec입니다. 회귀 탭은 금액(만원) OLS 탐색용입니다.",
    },
  ],
};

export const CLUSTER_FLOOR_INDEX_HELP: AnalysisExplain = {
  ...RESIDENTIAL_FLOOR_INDEX_HELP,
  spec_id: "cluster_floor_index_regression_static_v2",
  title: "층·면적 효용지수 (도로 cluster) — 이렇게 계산합니다",
  summary:
    "같은 도로명 cluster 실거래의 ln(㎡당단가)를 회귀합니다. 상가 층은 지하·1·2·저·중·고·초고층이고, 면적은 연면적 30㎡ 면적형(공장은 100/300/1000㎡)입니다. 1층 또는 중앙 면적형=100%. 회귀 탭과 숫자가 다릅니다.",
  formula:
    "ln(㎡당단가) = β₀ + ln(연면적, 면적형 탭 제외) + 연식 + 거래시점(반기) + (면적 탭이면 층구간) + (용도) + Σ γ_g·D_g · HC3",
  reference: "층=1층(화면) · 면적형=연면적 중앙값 칸",
  floor_groups: [
    "층별: B2 이하=지하심층, B1=지하1층, 1층=100%, 2층, 3–4=저층, 5–9=중층, 10–19=고층, 20+=초고층. 지하를 주거 중층부에 넣지 않습니다.",
    "면적별(상가): 연면적 30㎡ 반올림. 기준=표본 중앙값 칸.",
    "면적별(공장): 100㎡ 미만 · 100~300 · 300~1000 · 1000㎡ 이상. 30㎡ 눈금이 아닙니다.",
  ],
  controls: ["ln(연면적, 면적형 탭 제외)", "연식", "거래시점(반기)", "층 구간(면적 탭)", "건축물용도"],
  interpretation: [
    "지수는 비슷한 연면적·연식·시점에서의 층·면적 상대 수준입니다.",
    "평균 열은 원자료, 지수는 통제 후 %입니다.",
    "같은 도로 안 건물·입지 차이는 남습니다.",
  ],
  limitations: [
    "도로 cluster·기간 안 패턴 — 인과·적정가 아님",
    "구간 n<5 → 지수 없음, 칸 n<15 → 참고용",
    "회귀 탭(금액 OLS)과 숫자 불일치는 정상",
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

export const NEW_APT_EXPERIMENT_HELP: AnalysisExplain = {
  spec_id: "new_apartment_regression_track_a_v1",
  spec_version: "1",
  title: "신규아파트 회귀 실험 (트랙 A)",
  summary:
    "아직 없는 아파트를 어디에·어떤 상품으로 지으면 ㎡당 가격 수준이 어느 정도인지를 보는 실험입니다. " +
    "개별 분양가가 아니고, 기존 건물 「회귀 분석」 탭과도 숫자가 다릅니다. " +
    "대전 M2는 잠정 기준식이며, 충북 복제·대전 hold-out 고정 전이 전에는 최종으로 보지 않습니다.",
  formula:
    "ln(단지 중앙값 만원/㎡) = 연도 + ln(토지P50) + ln(세대수) + 최고층 + 세대당주차 + vintage   ← M2 대전 잠정",
  interpretation: [
    "토지 P50은 필지 실거래가가 아니라 읍×용도지역×대 5년 중앙값입니다. 시 전체 입지 수준을 잡습니다.",
    "세대수·층·주차·vintage는 「무엇을 짓는가」이고, 대전 hold-out 예측력의 대부분을 담당했습니다.",
    "시공사(M3)는 대전만으로는 표본이 얇습니다. 충북까지 연 뒤에 봅니다.",
    "구 아파트 P50은 입지와 겹치므로 본선에 넣지 않고 진단 비교에만 둡니다.",
    "대전+충북을 섞을 때는 지역 효과를 통제하고, 같은 대전 hold-out이 좋아지는지로 판단합니다. 전체 평균 MAPE만 보고 채택하지 않습니다.",
  ],
  limitations: [
    "현재 시뮬 본체는 대전 아파트. 충북은 같은 M2를 복제해 구조를 확인하는 단계입니다.",
    "비주거 도로 cluster에는 동일 트랙이 없습니다.",
    "점추정만으로 분양가를 단정하지 않습니다. 식·계수·n·경고·hold-out을 같이 봅니다.",
    "동 안에서 토지 분산이 작으면 동 내부 설명력은 낮아 보일 수 있습니다.",
    "연도 hold-out은 빠진 연도의 시장더미를 가장 가까운 학습 연도로 대체합니다.",
    "APE가 큰 단지는 연도 셀이 아니라 단지 단위로 보고, 노후 재고와 신축 hold-out을 나눕니다. M4를 바로 넣지 않습니다.",
  ],
  interpretation_hints: [],
  presets: [
    {
      id: "vs_building_reg",
      question: "건물 상세의 회귀 분석 탭과 무엇이 다른가요?",
      answer:
        "회귀 분석 탭은 그 단지(또는 코호트) 거래 한 건 한 건의 금액 OLS입니다. 이 실험은 단지×연도 중앙값으로 신규 단지 수준을 봅니다.",
    },
    {
      id: "why_m2",
      question: "왜 M2가 기준식인가요?",
      answer:
        "대전에서는 토지만으로는 hold-out 오차가 거의 안 줄고, 상품 변수를 넣으면 MAPE가 크게 내려갔습니다. " +
        "다만 대전만으로는 시공사·신축 대단지를 판단하기에 범위가 좁아, M2는 잠정입니다. 충북 복제와 대전 hold-out 고정 전이를 본 뒤에 확정 여부를 판단합니다.",
    },
    {
      id: "why_chungbuk",
      question: "충북을 넣으면 바로 식을 바꾸나요?",
      answer:
        "아닙니다. 통합 평균 MAPE가 좋아져도 충북 표본이 많거나 쉬워서일 수 있습니다. " +
        "같은 대전 hold-out이 좋아지는지를 보고, 나빠지면 지역 구조가 다르다고 보고 통합을 채택하지 않습니다.",
    },
  ],
  controls: ["연도 더미", "ln(토지P50)", "ln(세대수)", "최고층", "세대당 주차", "vintage"],
  floor_groups: [],
};

