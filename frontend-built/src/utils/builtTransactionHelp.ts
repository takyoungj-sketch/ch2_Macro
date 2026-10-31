import type { AnalysisExplain, BuiltTransactionRow } from "../types";

export const TRANSACTION_ZONE_HELP: AnalysisExplain = {
  spec_id: "built.transactions.zone_source", spec_version: "1", title: "거래목록의 용도지역",
  interpretation_hints: [], presets: [],
  summary: "실거래 자료의 용도지역을 우선 표시합니다. 보강을 켜면 원자료에 유효한 값이 없는 거래에 연결된 자료를 활용합니다.",
  interpretation: [
    "용도지역 옆 † 표시는 보강 자료를 사용한 셀입니다. 마우스를 올리면 출처를 확인할 수 있습니다.",
    "현재 보강 값은 계약연도 토지대장 자료를 사용합니다. 건축물대장의 연결 여부와 용도지역의 출처는 서로 다릅니다.",
  ],
  limitations: ["자료가 연결되지 않거나 확인할 수 없는 값은 임의로 채우지 않습니다."],
};

export const TRANSACTION_ASSESSED_PRICE_HELP: AnalysisExplain = {
  spec_id: "built.transactions.assessed_price", spec_version: "1", title: "거래목록의 개별공시지가",
  interpretation_hints: [], presets: [],
  summary: "연결된 필지의 개별공시지가를 원/㎡ 단위로 표시합니다. 부동산 전체의 거래금액이나 공시가격 총액이 아닙니다.",
  interpretation: [
    "계약연도와 같은 기준연도의 값을 우선하고, 없을 때 직전 연도 값을 사용합니다.",
    "계약연도와 기준연도가 같으면 금액만 표시합니다. 다르거나 계약연도를 확인할 수 없으면 기준연도도 함께 표시합니다.",
    "각 금액에 마우스를 올리면 기준연도와 계약연도를 확인할 수 있습니다.",
  ],
  limitations: ["기준연도가 같아도 계약 당시 이미 공개된 자료였다는 뜻은 아닙니다. 값이 없으면 임의로 채우지 않습니다."],
};

export function assessedPriceYearInfo(row: BuiltTransactionRow) {
  const dateYear = row.contract_date?.match(/^(\d{4})-/)?.[1];
  const contractYear = row.contract_year ?? (dateYear ? Number(dateYear) : null);
  const priceYear = row.assessed_land_price_year;
  return {
    suffix: priceYear && priceYear !== contractYear ? ` · ${priceYear}년 기준` : "",
    title: `개별공시지가(원/㎡) · 기준연도: ${priceYear ?? "미제공"} · 계약연도: ${contractYear ?? "미제공"}`,
  };
}
