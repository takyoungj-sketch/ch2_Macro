import type { AnalysisExplain } from "../types";

export function builtSettingsHelp(key: string, title: string, summary: string, interpretation: string[] = [], limitations: string[] = []): AnalysisExplain {
  return { spec_id: `built_settings_${key}`, spec_version: "1", title, summary, interpretation, limitations, interpretation_hints: [], presets: [] };
}

export const BUILT_TYPE_HELP = builtSettingsHelp("type", "유형 선택", "분석할 부동산 유형을 선택해 주세요.", [
  "기본 선택은 상업입니다. 공장·단독을 추가하면 여러 유형을 함께 분석합니다.",
  "유형을 바꾸면 해당 유형의 기본 변수와 표본 필터로 바뀝니다. 결과를 갱신하려면 통계분석을 다시 실행해 주세요.",
]);
export const BUILT_WINDOW_HELP = builtSettingsHelp("window", "롤링 구간", "직전 월말부터 거슬러 올라가 선택한 기간의 계약을 분석합니다.", [
  "3년·5년·7년 중 하나를 선택해 주세요. 조회 기간에 따라 거래 수와 분석 결과가 달라집니다.",
  "계약연도를 따로 지정한 경우에는 롤링 구간을 적용하지 않습니다.",
]);
export const BUILT_REGION_HELP = builtSettingsHelp("region", "지역 선택", "시도를 고른 뒤 시군구를 선택해 주세요.", [
  "읍·면·동을 선택하지 않으면 선택한 시군구 전체를 분석합니다.",
  "왼쪽에서는 기준 지역을 하나 선택합니다. 인접 지역은 오른쪽 지도에서 추가할 수 있습니다.",
  "지역 버튼의 괄호 안 숫자는 해당 조회 조건의 거래 수입니다. 결측치·지분·이상치 처리 뒤 실제 적합 표본 수와는 다를 수 있습니다.",
]);
export const BUILT_RI_HELP = builtSettingsHelp("ri", "법정리 선택", "선택한 읍·면·동 아래에 법정리 자료가 있으면 목록이 나타납니다.", [
  "법정리를 선택하지 않으면 읍·면·동 전체를 분석합니다. 선택한 법정리를 해제하면 읍·면·동 기준으로 돌아갑니다.",
  "왼쪽에서 하나를 선택하고, 인접 법정리는 오른쪽 지도에서 추가할 수 있습니다.",
  "법정리를 고르면 해당 법정리와 상위 지역을 기준으로 결과를 제공합니다.",
]);
export { BUILT_MISSING_HELP } from "./builtRegressionSettingsCopy";
export const BUILT_FILTER_HELP = builtSettingsHelp("filter", "표본 필터", "분석할 거래의 면적·연식·범주를 좁힙니다.", [
  "선택하지 않은 항목은 전체를 포함합니다. 필터는 회귀·거래목록·추정에 동일하게 적용됩니다.",
  "숫자 입력 옆 범위는 조회 자료의 최솟값과 최댓값입니다. 범주를 선택하면 해당 거래만 포함합니다.",
  "거래 수와 선택 상태를 확인한 뒤 통계분석을 다시 실행해 주세요.",
]);
export const BUILT_ENRICHMENT_HELP = builtSettingsHelp("enrichment", "건축물대장 정보 활용 기준", "연결이 확인된 건축물대장 정보만 분석에 활용합니다.", [
  "상업·공장은 건물 구조, 단독·다가구는 용도지역 등 기존 보강 정책에 따른 정보를 사용합니다. 구조·개별공시지가는 변수 선택에서도 체크해야 회귀에 반영됩니다.",
  "대장 자료가 계약 시점보다 뒤에 작성됐을 수 있습니다. 당시 건물 상태를 완전히 복원한 자료로 해석하지 마세요.",
  "연결되지 않거나 확인되지 않은 정보는 임의로 채우지 않습니다. 원장 자료와 기존 보강 정책은 유지됩니다.",
  "기준 연결률 75.0%는 2026-08-25 의사결정 D-050의 고정 집계입니다. 2019년 이후 거래 665,030건(지분 포함) 중 연결 498,568건을 기준으로 합니다.",
  "대상 거래 기간의 종료일은 이 고정 집계 자료에 별도로 제공되지 않습니다. 현재 선택 지역·조회 기간의 연결률이나 연결 정확도를 뜻하지 않습니다.",
]);
