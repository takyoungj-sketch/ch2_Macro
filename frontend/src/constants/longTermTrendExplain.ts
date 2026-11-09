import type { AnalysisExplain } from "../types";
import type { LongTermRegionTarget } from "../utils/longTermTargets";

const LEVEL_LABEL: Record<string, string> = { beopjungri: "법정동·리", eupmyeondong: "읍·면·동", sigungu: "시·군·구", city: "시 · 자치구 통합", sido: "시·도" };
export type LtPriceMetric = "mean" | "median";
export interface LongTermExplainContext {
  zoneType: string; landCategory: string; metric: LtPriceMetric; targets: LongTermRegionTarget[];
  yearFrom?: number | null; yearTo?: number | null; seriesCount?: number; referenceOnlyYears?: number;
}
export function buildLongTermTrendExplain(ctx: LongTermExplainContext): AnalysisExplain {
  const metricLabel = ctx.metric === "median" ? "중앙값" : "평균";
  const levelText = [...new Set(ctx.targets.map(t => t.region_level))].map(level => LEVEL_LABEL[level] ?? "선택 지역").join(", ") || "선택 지역";
  const seriesCount = ctx.seriesCount ?? ctx.targets.length;
  return {
    spec_id: "land.long_term_trend.v1", spec_version: "1.0", title: "토지 장기 추세 읽기",
    summary: `달력 연도별 ${metricLabel} 단가를 이어 토지 거래의 장기적인 흐름을 보여줍니다. 단위는 만원/㎡입니다.`,
    interpretation: ["선택한 용도지역·지목의 연도별 자료입니다. 도로·면적·지분·이상치 등 추가 필터는 적용하지 않습니다.",
      ctx.metric === "median" ? "중앙값과 25%·75% 값은 지역별로 표시하며, 여러 지역을 합친 중앙값 선은 제공하지 않습니다." : "지역이 여러 곳이면 지역별 평균과 거래 수로 가중한 통합 평균을 구분해서 보여줍니다.",
      "롤링 구간은 계약일 기준, 장기 추세는 1월~12월의 달력 연도 기준입니다. 같은 표본의 결과로 오해하지 않도록 기간부터 확인해 주세요."],
    limitations: ["거래가 15건 미만인 연도는 참고용으로 표시합니다. 거래 수와 분포를 함께 살펴봐 주세요.", "값이 없는 연도는 거래가 없거나 집계자료가 제공되지 않은 경우일 수 있습니다. 곧바로 0원이나 무거래로 해석하지 마세요.", "행정구역 개편이 있었던 지역은 자료 기간과 선택한 지역 단위를 함께 확인해 주세요. 현재 명칭이 과거에도 같은 경계를 뜻했다고 가정하지 마세요."],
    interpretation_hints: [`용도지역 × 지목: ${ctx.zoneType} · ${ctx.landCategory}`, `추세선: 연도별 ${metricLabel} · 만원/㎡`, `지역 단위: ${levelText} · 지역별 선 ${seriesCount}개${ctx.metric === "median" ? " · 중앙값 통합선 없음" : seriesCount >= 2 ? " · 통합 평균 별도 표시" : ""}`,
      ...(ctx.yearFrom != null && ctx.yearTo != null ? [`표시 연도: ${ctx.yearFrom}~${ctx.yearTo} · 1월~12월 기준`] : []),
      ...(ctx.referenceOnlyYears != null && ctx.referenceOnlyYears > 0 ? [`참고용 연도: ${ctx.referenceOnlyYears}개 · 거래 15건 미만`] : [])],
    formula: "단가(만원/㎡) = 거래금액(만원) ÷ 계약면적(㎡)\n" + (ctx.metric === "median" ? "중앙값은 단가를 크기순으로 나열한 가운데 값입니다. 짝수 건이면 가운데 두 값의 평균입니다. 중앙값과 25%·75% 값은 소수 첫째 자리로 반올림합니다." : "연도별 평균은 각 거래의 단가를 같은 비중으로 평균합니다. 여러 지역의 통합 평균은 지역별 평균에 거래 수를 가중한 값입니다."),
    controls: ["선택한 용도지역과 지목에 해당하는 사전 집계자료를 사용합니다.", "도로조건·면적구분·면적 범위·지분거래 제외·IQR 이상치 제외는 적용하지 않습니다.", "필터분석에서 선택한 연도와 별개로, 장기 추세에서 표시하는 연도 범위를 확인해 주세요.", "상위 행정구역 한 곳을 선택하면 해당 구역 전체 거래를 한 표본으로 집계한 선을 보여줍니다.", "중앙값에서 25·75 표시를 켜면 같은 표본의 분위수도 볼 수 있습니다. 축은 중앙값 기준을 유지하므로 그래프 밖의 값은 아래 표에서 확인해 주세요."],
    floor_groups: [],
    presets: [{ id: "vs-filter", question: "필터분석 결과와 왜 다른가요?", answer: "장기 추세에는 도로·면적·지분·이상치 등의 추가 필터가 적용되지 않습니다. 같은 용도지역·지목을 골랐더라도 기간과 분석 표본이 다를 수 있습니다." },
      { id: "metric", question: "평균과 중앙값은 어떻게 읽나요?", answer: "평균은 고가·저가 거래의 영향을 더 받습니다. 중앙값은 가운데 거래의 수준을 보여줍니다. 둘 중 하나만으로 전체 가격 분포나 개별 필지의 적정가격을 판단하지 마세요." },
      { id: "median-interp", question: "중앙값이 실제 한 거래의 단가와 다른 이유는 무엇인가요?", answer: "거래 수가 짝수이면 가운데 두 단가의 평균을 사용합니다. 분위수도 보간으로 실제 한 거래의 값과 다를 수 있습니다. 지분거래도 포함하므로 거래 구성을 함께 확인해 주세요." }],
  };
}
