import type { AiContextPayload } from "@ch2/ai-assistant/aiClient";
import type { RentAssetType, RentConversionRate, SangkwonAnnualResponse } from "../types";

export const RENT_CONVERSION_EXPLAIN = {
  spec_id: "rent_conversion_v1",
  spec_version: "1",
  title: "적용 전환율 (CH2 분석용)",
  summary:
    "같은 건물 전세·반전세로 건물별 r_b를 구한 뒤 지역·주택유형·연수 단순평균을 씁니다. 한국부동산원 공표값·고정 5%가 아닙니다.",
  formula: "r_b = 12M/(J−D) → r = 평균(r_b)",
  interpretation: [
    "2026-08 서울 hold-out에서 단순평균이 4방법 중 MAPE 전부 1위라 확정했습니다.",
    "환산 평균은 비교값이지 시세·적정 전세가 아닙니다.",
    "연립 건물 편차는 이질성이며 유형별 산식을 나누지 않습니다.",
  ],
  limitations: [
    "공식 전월세전환율이 아닙니다.",
    "게이트 미달 시 읍면동은 시군구 r로 대체합니다.",
  ],
  interpretation_hints: [],
  presets: [
    {
      id: "why_simple",
      question: "왜 단순평균인가요?",
      answer:
        "반전세→전세환산이 실제 전세 P50에 가까운지를 봤습니다. 서울 시군구·동 × 3·5·7년 hold-out MAPE에서 단순평균이 모두 1위, 원점회귀는 열위, 가중회귀가 가장 나빴습니다.",
    },
  ],
};

export function buildRentListContext(opts: {
  addr1: string;
  addr2: string;
  addr3?: string;
  windowYears: number;
  assetKinds: RentAssetType[];
  rates: RentConversionRate[];
  conversionApplied: boolean;
  conversionFallback?: boolean;
  conversionScope?: string;
  conversionMethod?: string;
}): AiContextPayload {
  const active = opts.rates.filter((r) => r.gate_passed && r.r_selected != null);
  const pick =
    opts.assetKinds.length === 1
      ? active.filter((r) => r.asset_type === opts.assetKinds[0])
      : active;
  const use = pick.length ? pick : active;
  const rSelected = use.length === 1 ? use[0].r_selected : null;
  const region = [opts.addr1, opts.addr2, opts.addr3].filter(Boolean).join(" ");
  return {
    app: "rent",
    panel: "RentListCard",
    purpose: "methodology",
    scope: {
      region_label: region,
      asset_type: opts.assetKinds[0],
      filters: {
        window_years: opts.windowYears,
        asset_types: opts.assetKinds,
        addr3: opts.addr3 || "",
      },
    },
    facts: {
      scope_label: region,
      window_years: opts.windowYears,
      r_selected: rSelected,
      conversion_applied: opts.conversionApplied,
      conversion_fallback: Boolean(opts.conversionFallback),
      conversion_scope: opts.conversionScope ?? "sigungu",
      conversion_method: opts.conversionMethod ?? "mean_simple",
      n_rates: use.length,
      rates: use.map((r) => ({
        asset_type: r.asset_type,
        r_selected: r.r_selected,
        n_buildings: r.n_buildings,
        scope: r.scope,
        fallback: r.fallback,
      })),
    },
    explain: RENT_CONVERSION_EXPLAIN,
  };
}

export const SANGKWON_REB_EXPLAIN = {
  spec_id: "sangkwon_reb_v1",
  spec_version: "1",
  title: "상업용 임대동향 상권 공표",
  summary:
    "한국부동산원 상업용부동산 임대동향조사입니다. 행정동이 아니라 상권 단위 표본 공표이며, 주거 전월세 원장·CH2 전환율과 섞지 않습니다.",
  formula:
    "기본표는 최신 분기 기준 4분기(1년) 롤링. 임대료 = 월단가 평균×12(만원/㎡) · NOI = 분기 합(만원/㎡) · 수익률 = ∏(1+r_q/100)−1. 추세선만 달력 연간.",
  interpretation: [
    "임대료는 시장 환산월세, 임대수입은 NOI 손익의 받은 수입입니다. 다른 수치입니다.",
    "공실로 못 받은 월세는 이미 임대수입·NOI 금액에 반영되어 있습니다. (1−공실)을 다시 곱하지 마세요.",
    "구성비 항등식: 임대수입% + 기타수입% − 운영경비% ≒ 순영업소득%.",
    "분기 I+C=T 이나 연간 복리 소득+자본이 연간 투자와 같지 않습니다.",
  ],
  limitations: [
    "표본 공표이며 개별 물건 가치·시세가 아닙니다.",
    "롤링 창에 4분기가 없으면 금액·수익률을 비웁니다. 추세선은 달력 연간입니다.",
    "상권 전환율은 상업용 공표용입니다. 주거 mean_simple과 다릅니다.",
    "감정평가·적정가·투자 판단을 하지 않습니다.",
  ],
  interpretation_hints: [],
  presets: [
    {
      id: "rent_vs_income",
      question: "임대료와 임대수입이 다른 이유는?",
      answer:
        "임대료는 (보증금×전환율/12)+월세를 면적으로 나눈 시장 단가입니다. 임대수입은 받은 월세·보증금 운용이익·관리비입니다. 임대료×순영업소득%로 NOI를 만들면 안 됩니다.",
    },
  ],
};

export function buildSangkwonContext(opts: {
  regionLabel: string;
  secNm: string;
  year: number | null;
  windowLabel?: string;
  rows: SangkwonAnnualResponse["rows"];
}): AiContextPayload {
  const compact: Record<string, Record<string, number | null>> = {};
  for (const row of opts.rows) {
    compact[row.metric] = row.values;
  }
  return {
    app: "rent",
    panel: "SangkwonCard",
    purpose: "methodology",
    scope: {
      region_label: `${opts.regionLabel} · ${opts.secNm}`,
      filters: { sec_nm: opts.secNm, year: opts.windowLabel || opts.year || "" },
    },
    facts: {
      scope_label: opts.regionLabel,
      sec_nm: opts.secNm,
      year: opts.year,
      window_label: opts.windowLabel || "",
      source: "reb_commercial_rent_survey",
      annual: compact,
    },
    explain: SANGKWON_REB_EXPLAIN,
  };
}
