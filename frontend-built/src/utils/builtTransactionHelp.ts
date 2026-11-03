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

export const TRANSACTION_ALLOCATION_HELP: AnalysisExplain = {
  spec_id: "built.transactions.allocation", spec_version: "1", title: "간이 토지배분단가",
  interpretation_hints: [], presets: [],
  summary: "토지와 건물을 함께 산 거래에서 추정 건물가를 빼고, 남은 금액을 토지 1㎡당 금액으로 나눠 보는 기능입니다.",
  interpretation: [
    "원가표를 조정한 뒤 ‘확인’을 누르면 목록에 원가·내용연수·배분단가가 표시됩니다.",
    "거래별 조정은 목록의 해당 칸을 누르세요. 따로 바꾼 값은 원가표를 수정해도 유지됩니다.",
    "이 버튼으로 다시 열 수 있습니다. 아래 표시 체크를 해제하고 확인하면 배분단가를 숨깁니다.",
  ],
  limitations: [
    "기본값은 CH2 Macro가 임의로 정한 가정입니다. 공식 원가표가 아니며, 실제 토지가격이나 감정평가 결과로 사용하지 마세요.",
    "지분거래와 음수 결과는 거래금액·면적의 기준과 원가 가정을 다시 확인하세요.",
    "‘확인’을 눌러야 적용됩니다. 거래 목록을 닫으면 초기화되며, CSV에는 포함되지 않습니다. 원본 거래자료는 바뀌지 않습니다.",
  ],
};

export const TRANSACTION_ALLOCATION_TABLE_HELP: AnalysisExplain = {
  spec_id: "built.transactions.allocation_table", spec_version: "1", title: "간이 신축원가표",
  interpretation_hints: [], presets: [],
  summary: "건물을 새로 짓는 비용과 사용할 수 있는 기간을 가정하는 표입니다. 기본값은 CH2 Macro가 간이 계산을 위해 임의로 정했으므로, 검토 목적에 맞게 확인하고 수정하세요.",
  interpretation: [
    "용도 16개와 구조 7개의 신축원가, 내용연수, 최소잔가(%)를 이 조회 안에서 조정합니다.",
    "구조가 없는 거래는 같은 용도의 하한 중 최솟값과 상한 중 최댓값을 범위로 쓰고, 내용연수는 그 구조들의 중앙값입니다.",
    "원가표를 고친 뒤 ‘확인’을 누르면 거래 목록에 적용됩니다.",
    "행에서 이미 고친 값은 간이 신축원가표를 바꿔도 유지됩니다. 그 행을 초기화하면 간이 신축원가표 값으로 돌아갑니다.",
    "최소잔가(%) 기본값은 10입니다. 잔존연수를 직접 넣은 거래에는 적용하지 않습니다. 간이 신축원가표 초기화는 CH2 Macro가 넣어 둔 처음 값으로 되돌립니다.",
  ],
  limitations: [
    "이 조회를 닫으면 조정 내용은 사라집니다.",
    "검토표 파일과 거래 자료는 바뀌지 않습니다.",
  ],
};

export const TRANSACTION_AGGREGATE_HELP: AnalysisExplain = {
  spec_id: "built.transactions.aggregate", spec_version: "1", title: "거래목록 집계",
  interpretation_hints: [], presets: [],
  summary: "불러온 거래를 묶어 건수와 단가를 봅니다. 대지 단가와 연면적 단가를 함께 보여 줍니다.",
  interpretation: [
    "1축은 구·읍, 읍·면·동, 리, 용도지역, 건축물용도, 도로조건, 계약연도 중 하나로 나눕니다. 유형을 둘 이상 고르면 유형이, 구조 더미나 개별공시지가를 켜면 구조가 추가됩니다. 고른 축이 비어 있으면 값이 있는 축으로 바꿉니다.",
    "2축 교차는 행과 열로 같은 거래를 나눕니다. 칸의 건수 아래 숫자는 중앙 단가이며, 앞이 대지, 뒤가 연면적입니다.",
    "대지 단가는 거래금액÷대지면적, 연면적 단가는 거래금액÷연면적입니다. 단위는 만원/㎡입니다. 면적이 없거나 0인 거래는 그 단가에서만 빠지고 건수에는 남습니다.",
    "행, 열, 칸을 누르면 목록이 그 조건만 보이도록 좁혀집니다.",
  ],
  limitations: ["집계는 모달에 불러온 거래만 사용합니다. 조회 건수가 불러온 상한을 넘으면 그 범위만 집계합니다."],
};

export const TRANSACTION_CSV_HELP: AnalysisExplain = {
  spec_id: "built.transactions.csv", spec_version: "1", title: "CSV보내기",
  interpretation_hints: [], presets: [],
  summary: "지금 조회 조건의 거래 목록을 CSV 파일로 받습니다.",
  interpretation: [
    "지역, 기간, 표본 필터가 파일에 반영됩니다. 구조 더미나 개별공시지가를 켠 경우에는 건축물대장 연결 정보도 들어갑니다.",
    "주소, 계약일, 용도, 구조, 금액, 면적 등 거래 목록 항목이 들어갑니다.",
    "화면에 일부만 불러온 경우에도 파일은 조회 조건의 거래를 담습니다. 5만 건을 넘으면 범위를 줄여야 내보낼 수 있습니다.",
  ],
  limitations: [
    "간이 토지배분단가로 계산한 신축원가, 내용연수, 토지 배분단가는 파일에 들어가지 않습니다.",
    "목록 화면의 정렬과 열 필터는 파일에 적용되지 않고, 조회 조건 그대로 내려받습니다.",
  ],
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
