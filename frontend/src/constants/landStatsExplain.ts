import type { AnalysisExplain, PaidAnalysisRequest, PaidAnalysisResponse, FreeStatsV2Response } from "../types";
import { statsAsOfLabel } from "../utils/freeStatsV2";

const UNIT_PRICE = "단가(만원/㎡) = 거래금액(만원) ÷ 계약면적(㎡)";
function help(id: string, title: string, summary: string, interpretation: string[], limitations: string[], extra: Partial<AnalysisExplain> = {}): AnalysisExplain {
  return { spec_id: id, spec_version: "1.0", title, summary, interpretation, limitations, interpretation_hints: [], presets: [], controls: [], floor_groups: [], ...extra };
}

export function buildLedgerPipelineExplain(): AnalysisExplain {
  return help("land.ledger_pipeline.v1", "토지 거래자료 정리 기준",
    "국토교통부 실거래가 공개자료를 정리해 통계와 거래목록에 사용합니다. 계약 취소·중복 신고·필수 정보 누락 등에 따라 원본 건수와 화면의 거래 수는 다를 수 있습니다.",
    ["계약면적·거래금액·지역·계약일 등 필수 정보가 유효한 거래를 사용합니다.", "해제 신고된 거래는 통계와 목록에서 제외합니다.", "정정·해제 신고는 자료 갱신 때 반영되므로 과거 수치가 달라질 수 있습니다."],
    ["원본 신고 오류나 지번 표기 차이를 모두 자동으로 바로잡을 수는 없습니다.", "행정구역이 개편된 지역은 선택한 지역 단위와 자료 기간을 함께 확인해 주세요."],
    { controls: ["통계와 거래목록에는 유효성 검사를 통과하고 단가를 계산할 수 있는 거래를 포함합니다.", "필터분석과 거래목록에는 사용자가 선택한 연도·도로·면적·용도지역·지목·지분·이상치 조건을 추가로 적용합니다."],
      floor_groups: ["원본 자료를 수집하고 필수 정보의 유효성을 확인합니다.", "해제 신고를 제외하고 동일 거래의 반복 신고를 정리합니다.", "지번·계약일·지분·거래유형 등 화면 표시 정보를 정리합니다.", "분석 목적에 맞게 기본통계와 연도별 통계를 집계합니다."],
      presets: [{ id: "cancel", question: "해제 신고란 무엇인가요?", answer: "계약이 해제됐다고 신고된 거래입니다. 정상 신고와 해제 신고가 함께 있으면 해제 신고 행을 통계에서 제외합니다." },
        { id: "dedupe", question: "중복 신고는 어떻게 정리하나요?", answer: "법정동·지번·계약일·면적·금액 등을 조합한 기준으로 동일 거래의 반복 신고를 묶고 최신 신고 한 건을 남깁니다. 원본의 표기 차이는 자동으로 합쳐지지 않을 수 있습니다." }] });
}

export interface FreeStatsExplainContext {
  data: FreeStatsV2Response; viewMode: "free" | "paid"; isPaidBasic: boolean; windowYears: 3 | 5 | 7; useUpper: boolean; upperLevelLabel?: string;
}
export function buildFreeStatsExplain(ctx: FreeStatsExplainContext): AnalysisExplain {
  const period = `${ctx.data.period_start?.slice(0, 10) ?? "시작일 미제공"} ~ ${ctx.data.period_end?.slice(0, 10) ?? "종료일 미제공"}`;
  return help("land.free_stats_v2.v1", "토지 기본통계 읽기",
    `선택 지역의 최근 ${ctx.windowYears}년 토지 거래를 요약합니다. 연도별 표와 용도지역 × 지목 분석표에서 거래 규모와 단가 분포를 살펴볼 수 있습니다.`,
    ["평균·중앙값·분위수 단가는 만원/㎡ 단위입니다. 연도별 표의 가중 단가와 구분해서 읽어 주세요.", "롤링 구간은 계약일 기준입니다. 첫해와 마지막 해가 1월~12월 전체를 포함하지 않을 수 있습니다.", "도로·면적·지분·이상치 등의 추가 조건은 필터분석에서 확인할 수 있습니다."],
    ["상위 행정구역만 선택하면 산하 지역을 합산한 통계입니다.", "자료가 없어 표시되지 않는 값과 거래 수가 0인 경우를 구분해 주세요."],
    { formula: UNIT_PRICE, controls: ["유효한 거래 중 해제 신고를 제외하고 단가를 계산할 수 있는 거래를 집계합니다.", "기본통계에는 도로·면적·지분·IQR 등의 추가 필터를 적용하지 않습니다.", "연도별 인구는 별도 인구자료의 연말 값을 사용합니다. 자료가 없는 연도는 빈칸으로 표시합니다."],
      floor_groups: ["연도별 표에서 거래 수·총거래금액·계약면적과 가중 단가를 확인합니다.", "분석표는 용도지역과 지목 또는 지목군별 거래를 나눠 보여줍니다. 칸 안의 값은 범례 도움말에서 확인해 주세요."],
      interpretation_hints: [`기준: ${statsAsOfLabel(ctx.data) ?? "미제공"}`, `롤링 구간: 최근 ${ctx.windowYears}년 · 계약일 기준`, `집계 기간: ${period}`, `표본: ${ctx.data.total.count.toLocaleString("ko-KR")}건`, ...(ctx.useUpper && ctx.upperLevelLabel ? [`상위 행정구역 합산: ${ctx.upperLevelLabel}`] : [])],
      presets: [{ id: "vs-filter", question: "필터분석과 무엇이 다른가요?", answer: "기본통계는 선택한 롤링 구간의 거래를 요약합니다. 필터분석은 선택 연도와 도로·면적·지분·이상치 등 추가 조건을 적용하므로 기간과 표본이 다를 수 있습니다." }, { id: "year-table", question: "연도별 표는 어느 날짜를 기준으로 하나요?", answer: "연도별 참고표는 각 달력 연도(1월~12월)를 요약합니다. 매트릭스는 선택한 롤링 구간의 시작일부터 종료일까지 집계하므로 양 끝 연도의 기간과 거래 건수가 다를 수 있습니다." }] });
}

export interface PaidFilteredExplainContext { result: PaidAnalysisResponse; regionLabel?: string }
export function buildPaidFilteredExplain(ctx: PaidFilteredExplainContext): AnalysisExplain {
  const req = ctx.result.request;
  const years = req.years?.length ? [...req.years].sort((a, b) => a - b).join(", ") : req.year_from != null && req.year_to != null ? `${req.year_from}~${req.year_to}` : "전체";
  return help("land.paid_filtered.v1", "필터분석 결과 읽기",
    "선택한 지역·연도와 추가 조건을 만족하는 거래의 단가 분포를 보여줍니다. 기본통계와 기간이나 표본이 다를 수 있습니다.",
    ["선택 연도는 계약연도 기준입니다. 계약일 기준의 롤링 구간과 비교할 때는 기간부터 확인해 주세요.", "분석표의 칸을 누르면 해당 용도지역과 지목의 추이·분포·거래목록을 확인할 수 있습니다."],
    ["거래가 적은 칸은 단가와 분위수가 크게 달라질 수 있습니다.", "기본통계에서 정한 후보 거래를 유지하는 분석에서는 그 후보 안에서 필터를 적용합니다."],
    { formula: UNIT_PRICE, controls: filterControlsList(req), interpretation_hints: [`기준: ${statsAsOfLabel(ctx.result) ?? "미제공"}`, `선택 연도: ${years}`, `표본: ${ctx.result.total.count.toLocaleString("ko-KR")}건`, `이상치 제외: ${req.exclude_outlier ? `적용 · IQR ${req.outlier_iqr_multiplier}배` : "적용 안 함"}`, `지분거래: ${req.exclude_partial ? "제외" : "포함"}`, `거래유형: ${req.deal_types?.length ? req.deal_types.join(", ") : "중개거래·직거래 전체"}`, ...(ctx.regionLabel ? [`지역: ${ctx.regionLabel}`] : [])],
      presets: [{ id: "outlier", question: "이상치 제외는 무엇인가요?", answer: "단가 분포의 25%~75% 구간 폭에 선택한 배수를 적용해 범위를 크게 벗어난 거래를 제외합니다. 선택한 거래목록·분포에도 같은 정책을 적용합니다. 제외된 거래가 잘못된 신고라는 뜻은 아닙니다." }] });
}
function filterControlsList(req: PaidAnalysisRequest): string[] {
  const items = ["유효한 거래 중 해제 신고를 제외하고 단가를 계산할 수 있는 거래를 사용합니다."];
  if (req.road_conditions?.length) items.push(`도로: ${req.road_conditions.join(", ")}`);
  if (req.deal_types?.length) items.push(`거래유형: ${req.deal_types.join(", ")}`);
  if (req.area_categories?.length) items.push(`면적구분: ${req.area_categories.join(", ")}`);
  if (req.area_sqm_min != null || req.area_sqm_max != null) items.push(`면적(㎡): ${req.area_sqm_min ?? "제한 없음"} ~ ${req.area_sqm_max ?? "제한 없음"}`);
  if (req.zone_types?.length) items.push(`용도지역: ${req.zone_types.join(", ")}`);
  if (req.land_categories?.length) items.push(`지목: ${req.land_categories.join(", ")}`);
  return items;
}

export function buildMatrixLegendExplain(): AnalysisExplain {
  return help("land.matrix_legend.v1", "분석표의 수치와 색상",
    "용도지역과 지목이 만나는 각 칸에서 거래 수와 단가 분포를 함께 확인할 수 있습니다. 단가의 단위는 만원/㎡입니다.",
    ["중앙값은 가운데 거래의 단가입니다. 평균과 차이가 크면 분포가 한쪽으로 치우쳤을 수 있습니다.", "평균 숫자의 파란색 진하기는 같은 지목 열 안에서 거래가 많은 정도입니다. 가격의 높낮이를 뜻하지 않습니다.", "연한 녹색 배경은 15건 이상인 칸의 표본 기준 표시입니다. 5건 미만인 칸은 흐리게 표시합니다."],
    ["95% 신뢰구간은 평균 단가에 대한 범위이며 중앙값의 범위가 아닙니다.", "표본 수나 강조색이 개별 필지의 가격 정확성을 보장하지는 않습니다."],
    { formula: UNIT_PRICE, floor_groups: ["1행: 거래 수 · 최솟값", "2~3행: 평균 · 25% 값 / 중앙값", "4행: 표준편차 · 75% 값", "5행: 평균의 95% 신뢰구간 · 최댓값"], controls: ["평균 숫자의 진하기는 거래 수 상위 30%·중간 40%·하위 30%에 따라 구분합니다. 해당 열에서 거래가 있는 칸이 5곳 미만이면 같은 기본 파랑으로 표시합니다.", "행·열 머리의 거래 수와 평균은 해당 축 전체의 합산 결과입니다.", "거래가 없거나 값을 제공하지 않는 칸은 대시로 표시하며 0원으로 채우지 않습니다."], presets: [{ id: "ci", question: "평균의 95% 신뢰구간은 무엇인가요?", answer: "표본으로 추정한 평균 단가의 불확실성을 나타내는 t-구간입니다. 개별 필지의 거래 단가 범위가 아니며, 표본이 적으면 넓어질 수 있습니다." }] });
}
export function buildMatrixTableExplain(): AnalysisExplain {
  return help("land.matrix_table.v1", "용도지역 × 지목 분석표",
    "선택한 거래를 용도지역(행)과 지목 또는 지목군(열)으로 나눠 비교하는 표입니다.",
    ["칸 안의 수치와 색상은 범례 도움말에서 확인해 주세요.", "상세 보기가 가능한 칸을 누르면 해당 거래의 추이·분포·목록을 볼 수 있습니다.", "미지정·기타는 원자료의 분류 정보가 없거나 분류 규칙에 따라 묶인 거래입니다."],
    ["전체 합산 칸과 개별 칸의 단순 합은 다를 수 있습니다. 표에 표시된 분석 범위를 확인해 주세요.", "표본이 적은 칸은 평균뿐 아니라 중앙값·분위수도 신중하게 읽어 주세요."]);
}

export interface TransactionListExplainContext { zoneType: string; landCategory: string; total?: number; loadedCount?: number; excludeOutlier: boolean; outlierMultiplier: number; filterSummary?: string }
function transactionHints(ctx: TransactionListExplainContext): string[] {
  return [`용도지역 × 지목: ${ctx.zoneType} · ${ctx.landCategory}`, ...(ctx.total != null ? [`전체 조회 대상: ${ctx.total.toLocaleString("ko-KR")}건`] : []), ...(ctx.loadedCount != null ? [`화면에 불러온 거래: ${ctx.loadedCount.toLocaleString("ko-KR")}건`] : []), `이상치 제외: ${ctx.excludeOutlier ? `적용 · IQR ${ctx.outlierMultiplier}배` : "적용 안 함"}`];
}
export function buildTransactionListExplain(ctx: TransactionListExplainContext): AnalysisExplain {
  return help("land.tx_list.v1", "거래목록 이용 방법",
    "현재 분석 조건에 해당하는 거래를 최신 계약 순으로 보여줍니다. 화면에서는 최대 1만 건을 불러와 필터와 정렬을 적용합니다.",
    ["계약일·지번·면적·지분·거래유형 등 개별 거래의 조건을 확인해 주세요.", "계약일이 없는 자료는 계약 연·월로 표시될 수 있습니다.", "집계표의 행이나 칸을 선택하면 해당 조건으로 거래목록을 좁힐 수 있습니다."],
    ["전체 조회 대상이 1만 건을 넘으면 화면의 목록과 집계는 불러온 거래만 반영합니다. CSV 내보내기는 같은 분석 조건의 전체 거래를 대상으로 합니다.", "기본통계나 장기 추세와 기간·필터가 다르면 거래 수가 달라질 수 있습니다."],
    { formula: UNIT_PRICE, controls: [...(ctx.filterSummary ? [ctx.filterSummary] : []), "화면의 목록은 불러온 거래에 필터·정렬·페이지 구분을 적용합니다. 한 페이지에 100건을 표시합니다.", `이상치 제외: ${ctx.excludeOutlier ? `단가 분포의 IQR ${ctx.outlierMultiplier}배 기준` : "적용 안 함"}`], interpretation_hints: transactionHints(ctx), presets: buildLedgerPipelineExplain().presets });
}
export function buildTransactionAggregateExplain(ctx: TransactionListExplainContext): AnalysisExplain {
  return help("land.tx_aggregate.v2", "거래 집계표 읽기",
    "거래목록에 불러온 자료를 한 가지 기준으로 묶거나 두 가지 기준의 교차표로 요약합니다.",
    ["읍·면·동·도로·거래유형·계약연도 등 묶을 기준을 선택할 수 있습니다.", "교차표는 거래 수와 중앙단가를 표시합니다. 단위는 만원/㎡입니다.", "행·칸·머리글을 선택하면 해당 조건으로 거래목록을 좁힐 수 있습니다."],
    ["집계는 화면에 불러온 거래만 사용합니다. 1만 건을 넘는 전체 조회 대상의 집계와 다를 수 있습니다.", "거래 구성이 다르면 단가가 달라질 수 있습니다. 표의 차이만으로 특정 조건의 인과적 효과를 판단하지 마세요."],
    { formula: UNIT_PRICE, controls: ["한 가지 기준의 집계에는 거래 수·중앙단가·평균단가·면적 합계를 표시합니다.", "기본 정렬은 거래 수가 많은 순이며 같은 건수에서는 이름순입니다.", ...(ctx.filterSummary ? [ctx.filterSummary] : [])], interpretation_hints: transactionHints(ctx) });
}
export function buildMatrixCellTrendExplain(isRolling: boolean): AnalysisExplain {
  return help("land.matrix_cell_trend.v1", isRolling ? "롤링 구간별 추이" : "선택 연도별 추이",
    isRolling ? "롤링 기간을 12개월 구간으로 나눠 단가와 거래 수의 흐름을 보여줍니다." : "선택한 계약연도별 평균 단가와 거래 수의 흐름을 보여줍니다.",
    [isRolling ? "평균 또는 중앙값을 선택할 수 있습니다. 중앙값에서 25·75 표시를 켜면 같은 표본의 25%·75% 값도 볼 수 있습니다." : "실선은 평균 단가, 점선은 거래 수입니다.", "단가의 단위는 만원/㎡입니다. 분포·거래목록과 같은 필터·이상치 정책을 사용합니다."],
    ["거래가 없는 연도나 구간은 점이 비어 있습니다.", "장기 추세는 달력 연도별 자료이며 추가 필터가 다를 수 있습니다. 같은 기간·표본인지 확인한 뒤 비교해 주세요."]);
}
export function buildHistogramExplain(): AnalysisExplain {
  return help("land.matrix_histogram.v1", "단가 분포 읽기",
    "선택한 거래가 어느 단가 구간에 모여 있는지 막대와 박스플롯으로 보여줍니다.",
    ["가로축은 단가(만원/㎡), 세로축은 거래 수입니다.", "상자는 25%~75% 구간, 파란 선은 중앙값, 수염은 최솟값과 최댓값입니다.", "이상치 제외를 선택하면 같은 조건의 거래를 제외한 뒤 막대와 박스플롯을 함께 그립니다."],
    ["표본이 적으면 그래프 모양이 불안정할 수 있습니다. 한 건이면 여러 통계값이 같은 위치에 겹칩니다.", "특정 구간의 분포와 여러 구간을 합친 전체 분포는 구분해서 읽어 주세요."]);
}

export const LAND_REGRESSION_HELP = help("land.regression.v1", "토지 회귀 결과 읽기",
  "현재 용도지역·지목과 분석 조건에 해당하는 거래로 변수와 토지 단가의 관계를 분석합니다.",
  ["분석 대상은 거래금액이 아닌 단가 또는 로그 단가입니다. 선형모형의 단가는 만원/㎡ 단위입니다.", "선택한 변수라도 자료가 부족하거나 값에 차이가 없으면 제외될 수 있습니다. 실제 포함 변수와 기준 범주를 결과에서 확인해 주세요.", "결정계수와 학습 오차는 이 표본 안의 결과입니다. 새로운 거래의 정확도를 보장하지 않습니다."],
  ["계수는 통계적 관계이며 인과관계나 개별 필지의 적정가격을 뜻하지 않습니다.", "개별공시지가를 사용하면 해당 정보가 있는 표본만 분석에 남을 수 있습니다. 지분거래의 공시지가는 임의로 보강하거나 채우지 않습니다."],
  { formula: "단가 또는 로그 단가 ~ 선택한 변수", controls: ["면적·도로조건·거래유형·지분·연도·법정동 등 선택한 변수를 사용합니다.", "결측치와 이상치 처리에 따라 실제 적합 거래 수가 달라질 수 있습니다.", "법정동 고정효과는 기준 동과의 단가 수준 차이를 구분하는 변수입니다."], presets: [{ id: "log_vs_linear", question: "선형모형과 로그모형은 어떻게 읽나요?", answer: "선형모형은 단가의 차이를 원래 단위로, 로그모형은 상대적인 변화를 중심으로 읽습니다. 변수에도 로그를 적용했는지 확인하고 계수 표의 효과 해석을 참고해 주세요. 모형 종류만으로 정확도를 판단하지 마세요." }] });
export const LAND_PREDICT_HELP = help("land.predict.v1", "토지 조건별 추정",
  "적합한 회귀모형에 조건을 입력해 통계적 추정 단가와 범위를 확인합니다. 단위는 만원/㎡입니다.",
  ["계약연도는 올해, 거래유형은 중개거래를 자동 적용합니다. 해당 효과가 회귀식에 포함된 경우에 적용되며, 추정 기준은 입력칸 위에서 확인할 수 있습니다.", "연도추세가 없으면 현재 시점으로 보정하지 않습니다. 거래유형 효과가 없으면 중개거래만의 가격으로 구분할 수 없습니다. 모형에 거래유형 효과가 있지만 중개거래 범주가 없다면 추정을 제공하지 않습니다.", "95% 평균 추정범위는 입력 조건에서 평균적인 단가 수준의 불확실성입니다.", "95% 개별 거래 예측범위는 개별 거래의 변동까지 고려합니다.", "분석에 사용한 변수의 범위를 벗어난 입력은 외삽이므로 결과를 신중하게 읽어 주세요."],
  ["이 결과는 AVM에 의한 가격평가가 아닌, 회귀모형의 통계적 참고값입니다.", "표시한 범위가 실제 거래 단가를 보장하지는 않습니다."],
  { formula: "추정값 = 입력 조건과 회귀계수로 계산한 값", presets: [{ id: "pi_ci", question: "두 범위는 어떻게 다른가요?", answer: "평균 추정범위는 평균적인 단가 수준의 불확실성을, 개별 거래 예측범위는 개별 거래의 변동까지 고려합니다. 둘 다 개별 필지의 적정가격을 보장하는 범위는 아닙니다." }] });
export const LAND_MODEL_SUGGEST_HELP = help("land.model_suggest.v1", "토지 모형 추천 읽기",
  "기존 표본에서 변수 조합을 비교해 설명형과 예측형 후보를 보여줍니다. 추천은 비교를 돕는 참고 결과입니다.",
  ["설명형은 AIC로 적합도와 모형의 복잡도를 함께 살펴봅니다.", "예측형의 MAPE는 학습 자료 안의 오차입니다. 새로운 거래를 따로 검증한 오차로 해석하지 마세요.", "선택한 후보의 실제 변수와 적용 후 분석 조건을 함께 확인해 주세요."],
  ["표본과 종속변수 척도가 다른 지표는 직접 비교하지 마세요.", "후보 순위가 개별 필지의 가격 정확성을 보장하지는 않습니다."]);
export const LAND_SCATTER_RAW_HELP = help("land.scatter_raw.v1", "상관관계 · 다른 변수 고려 전",
  "각 변수와 토지 단가가 실제 거래에서 어떻게 함께 분포하는지 보여줍니다.",
  ["가로축의 변수와 세로축의 단위, 거래 수를 먼저 확인해 주세요.", "상관계수 r은 두 변수의 선형적인 관계를 나타냅니다. 다른 변수의 영향은 함께 섞여 있습니다."],
  ["상관관계만으로 인과관계를 판단할 수 없습니다. 다른 변수의 영향을 고려한 관계는 부분회귀도에서 확인해 주세요."], { formula: "r = 변수와 단가 사이의 상관계수" });
export const LAND_SCATTER_PARTIAL_HELP = help("land.scatter_partial.v1", "부분회귀도 · 다른 변수 고려 후",
  "모형에 포함된 다른 변수의 영향을 각각 제거한 뒤, 관심 변수와 단가의 관계를 살펴봅니다.",
  ["파란 선의 기울기는 해당 변수의 회귀계수와 같습니다.", "부분 R²는 다른 변수를 고려한 뒤 관심 변수가 추가로 설명하는 정도를 참고하는 값입니다."],
  ["연속 변수에 제공하며, 로그모형에서는 로그 단가의 잔차를 사용합니다.", "모형 전체의 오차 분포나 영향 거래를 진단하는 잔차 진단과는 다릅니다."], { formula: "다른 변수의 영향을 제거한 관심 변수와 단가의 잔차를 비교합니다." });


export const LAND_REGRESSION_RESULT_HELP = help("land.regression.result.v1", "토지 회귀 결과 읽기",
  "선택한 거래자료에서 토지 단가와 각 조건의 관계를 분석한 결과입니다. 단위는 만원/㎡입니다.",
  ["결정계수와 조정 R²는 모형의 적합도를 나타냅니다. 로그 모형에서는 로그 단가 기준입니다. 현재 토지 회귀 결과는 학습 MAPE와 교차검증 MAPE를 제공하지 않습니다.",
   "회귀식은 절편과 p<0.1인 항을 먼저 표시합니다. 전체보기를 누르면 유의하지 않은 항도 확인할 수 있습니다. 조건별 추정은 전체 적합 모형으로 계산합니다.",
   "범주형 계수는 회귀식 아래의 기준 범주와 비교합니다. 법정동 고정효과의 상세 계수는 계수표에서 펼쳐볼 수 있습니다.",
   "면적과 단가 모두 로그를 적용한 모형에서 면적 계수는 면적 1% 변화에 따른 단가의 대략적인 % 변화입니다. 개별공시지가는 로그 변환한 원/㎡ 값을 사용합니다.",
   "연도추세는 학습 자료의 평균 계약연도를 기준으로 계산합니다. 회귀식의 연도 항에는 이 기준을 뺀 값을 적용합니다."],
  ["적합도가 높아도 새로운 거래에서 오차가 작다는 뜻은 아닙니다. 통계적 관계를 인과관계나 개별 필지의 적정가격으로 해석하지 마세요.",
   "공시지가 모형은 보강할 수 없는 지분거래와 공시지가 미연결 거래를 제외합니다. 확인되지 않은 공시지가는 임의로 채우지 않습니다. 연결 현황과 최종 적합 거래 수는 다른 단계의 수치입니다.",
   "복수 용도지역에 걸친 필지는 원본 자료의 제1용도지역을 사용합니다. 이 값이 면적 비중이나 가격 영향이 가장 큰 용도지역을 뜻하지는 않습니다."]);
