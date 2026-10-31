import type { AnalysisExplain } from "../types";

export type SettingsHelpSection = {
  title: string;
  entries: { label?: string; text: string }[];
  bullets?: boolean;
  collapsed?: boolean;
};
export type SettingsHelpCopy = {
  explain: AnalysisExplain;
  sections: SettingsHelpSection[];
};

function help(id: string, title: string, summary: string, sections: SettingsHelpSection[]): SettingsHelpCopy {
  return {
    explain: {
      spec_id: id, spec_version: "3", title, summary,
      interpretation: sections.flatMap(section => section.entries.map(entry => `${entry.label ? `${entry.label}: ` : ""}${entry.text}`)),
      limitations: [], interpretation_hints: [], presets: [],
    }, sections,
  };
}

const variables = help("built_var_select_v1", "변수 선택",
  "회귀분석에 사용할 변수를 선택합니다. 거래금액과 각 변수의 관계를 분석하며, 선택한 변수가 실제 회귀식에 포함되었는지는 분석 결과에서 확인할 수 있습니다.", [
    { title: "변수의 종류", entries: [
      { label: "연면적·대지면적·연식", text: "건물의 규모와 경과연수가 거래금액과 어떤 관계가 있는지 분석합니다." },
      { label: "용도지역·건축물용도·도로조건 등", text: "각 범주에 따른 거래금액의 차이를 분석합니다. 기준 범주와 비교하여 결과를 표시합니다." },
      { label: "구조·개별공시지가", text: "건축물대장 보강을 켜고 관련 정보가 확인되는 경우 활용할 수 있습니다." },
    ] },
    { title: "알아두세요", bullets: true, entries: [
      { text: "변수를 변경한 뒤에는 통계분석을 다시 실행해야 결과에 반영됩니다." },
      { text: "선택한 변수라도 자료가 부족하면 제외될 수 있습니다. 다른 변수와 구분하기 어려운 경우에는 계수 해석에 제한이 생길 수 있습니다." },
      { text: "변수를 많이 선택한다고 모형의 정확도가 반드시 높아지는 것은 아닙니다." },
    ] },
  ]);

const model = help("built_response_scale_v1", "회귀모형 선택",
  "거래금액과 변수의 관계를 어떤 방식으로 분석할지 선택합니다. 같은 자료라도 모형에 따라 회귀계수와 추정 결과가 달라질 수 있습니다.", [
    { title: "모형별 특징", entries: [
      { label: "선형회귀", text: "거래금액을 원래 단위로 분석합니다. 예를 들어 연면적의 계수가 200이라면, 다른 조건이 같을 때 연면적 1㎡ 증가에 따른 추정금액의 차이를 200만원으로 해석합니다." },
      { label: "로그회귀(log)", text: "거래금액에 로그를 적용합니다. 변수 변화에 따른 거래금액의 상대적 변화를 분석하는 데 적합합니다." },
      { label: "로그-로그 회귀(log-log)", text: "거래금액과 연면적·대지면적 등 일부 연속변수에 로그를 적용합니다. 면적이 1% 변할 때 거래금액이 대략 몇 % 변하는지 살펴볼 수 있습니다." },
    ] },
    { title: "알아두세요", bullets: true, entries: [
      { text: "로그를 적용하는 변수에는 양수 값이 필요합니다." },
      { text: "어떤 모형이 더 적합한지는 자료의 특성과 분석 목적에 따라 달라집니다." },
      { text: "모형별 회귀계수는 단위와 의미가 다르므로 단순히 크기만 비교해서는 안 됩니다." },
    ] },
    { title: "로그 적용 범위 더 보기", collapsed: true, entries: [
      { text: "log-log는 연면적이나 대지면적을 하나 이상 선택해야 사용할 수 있습니다. 연식과 범주형 변수는 로그로 바꾸지 않습니다." },
      { text: "개별공시지가는 선택한 모형 종류와 관계없이 로그로 사용합니다. 계수 표의 효과 해석에는 기존의 정확한 변환을 적용합니다." },
    ] },
  ]);

const missing = help("built_settings_missing", "결측치 처리",
  "선택한 범주형 변수에 정보가 없는 거래를 어떻게 처리할지 결정합니다.", [
    { title: "처리 방법", entries: [
      { label: "미상 범주 유지 (기본값)", text: "정보가 없는 거래를 ‘미상’이라는 별도 범주로 분류하여 분석에 포함합니다." },
      { label: "결측 거래 제외", text: "선택한 범주형 변수의 정보가 없는 거래를 분석에서 제외합니다. 분석에 사용되는 거래 수가 줄어들 수 있습니다." },
    ] },
    { title: "알아두세요", entries: [
      { text: "연면적·대지면적 등 숫자 변수의 결측 처리에는 적용되지 않습니다. 실제 제외 내역은 분석 결과에서 확인할 수 있습니다." },
    ] },
  ]);

const sample = help("built_sample_v1", "분석 표본",
  "회귀분석에 포함할 거래를 선택합니다. 화면의 거래 건수와 실제 회귀분석에 사용되는 건수는 다를 수 있습니다.", [
    { title: "선택 항목", entries: [
      { label: "지분거래 포함", text: "토지나 건물의 일부 지분만 거래된 사례를 분석에 포함할지 선택합니다. 지분거래는 전체 부동산의 거래와 가격 형성 방식이 다를 수 있습니다." },
      { label: "건축물대장 보강", text: "건축물대장 등에서 확인된 정보를 거래자료에 추가합니다. 이를 통해 건물 구조 등의 변수를 분석에 활용할 수 있습니다. 연결되지 않은 정보는 임의로 채우지 않습니다." },
      { label: "IQR 금액 이상치 제외", text: "거래금액이 다른 거래들과 크게 차이 나는 사례를 통계적 기준에 따라 제외합니다. IQR은 거래금액 분포의 가운데 50% 범위를 기준으로 이상치를 판별하는 방법입니다. 일반적으로 1.5배 기준이 3배 기준보다 더 많은 거래를 제외할 수 있습니다." },
    ] },
    { title: "알아두세요", bullets: true, entries: [
      { text: "분석 표본을 변경하면 회귀계수와 추정 결과가 달라질 수 있습니다." },
      { text: "이상치로 분류된 거래가 반드시 잘못된 거래라는 뜻은 아닙니다." },
      { text: "실제 분석에 사용된 거래 수와 제외 내역은 결과 화면에서 확인할 수 있습니다." },
    ] },
    { title: "유형별 적용 차이", collapsed: true, entries: [
      { text: "지분거래는 기본적으로 분석에서 제외하며 거래목록에는 남습니다. 단독·다가구는 원자료에 지분 구분이 없어 이 선택의 적용 대상이 아닙니다." },
    ] },
  ]);

export const BUILT_VAR_SELECT_HELP = variables.explain;
export const BUILT_RESPONSE_SCALE_HELP = model.explain;
export const BUILT_MISSING_HELP = missing.explain;
export const BUILT_SAMPLE_HELP = sample.explain;
export const BUILT_SETTINGS_COPY: Record<string, SettingsHelpCopy> = Object.fromEntries(
  [variables, model, missing, sample].map(copy => [copy.explain.spec_id, copy]),
);
