import type { AnalysisExplain, PaidAnalysisRequest, PaidAnalysisResponse } from "../types";
import type { FreeStatsV2Response } from "../types";
import { statsAsOfLabel } from "../utils/freeStatsV2";

/** 국토부 원장 → DB 거래 정제 파이프라인 (거래목록·통계 공통). */
export function buildLedgerPipelineExplain(): AnalysisExplain {
  return {
    spec_id: "land.ledger_pipeline.v1",
    spec_version: "1.0",
    title: "국토부 원본 → 거래 DB 정제 과정",
    summary:
      "통계·거래목록은 국토교통부 실거래가 공개 원본(CSV/엑셀)을 일정한 규칙으로 정제한 land_transactions 를 사용합니다. " +
      "아래 단계를 거친 뒤에만 집계·목록에 포함됩니다.",
    floor_groups: [
      "1) 수집·적재: 시도·연도별 원본 파일 → land_transactions (원본 행 보존)",
      "2) 유효성: 계약면적·거래금액·법정동코드·계약일 등 필수값 검증 → is_valid",
      "3) 해제 제외: 동일 물건에 대한 해제(취소) 신고 행은 is_cancelled=true 로 표시하고 통계·목록에서 제외",
      "4) 중복 정리: 동일 물건·계약 조건으로 판단되는 중복 신고는 transaction_hash 기준으로 묶고, 최신 신고 1건만 유효 표본으로 남김",
      "5) 표시 필드: 지번(lot_display), 계약일, 지분·거래유형 등 UI 표시용 컬럼 채움",
      "6) 사전집계: 기본통계(V2)·매트릭스·장기추세 등 용도별 마트 테이블 생성",
    ],
    controls: [
      "통계·목록 공통 포함: is_valid=true, is_cancelled=false, unit_price_per_sqm IS NOT NULL",
      "필터분석·목록 추가: 선택 연도·도로·면적·용도·지목·지분·IQR 이상치 등 사용자 필터",
    ],
    interpretation: [
      "원본 건수와 화면 건수가 다를 수 있습니다 — 해제·중복·유효성 미달 행이 빠지기 때문입니다.",
      "월간 갱신 시 최근 분기 CSV를 다시 받아 같은 키로 UPSERT 하며 해제·정정분을 반영합니다.",
    ],
    limitations: [
      "중복 판정은 설계된 business key(법정동·지번·계약·면적·금액 등)에 따릅니다. 국토부 신고 오류·지번 표기 차이는 자동으로 합치지 못할 수 있습니다.",
      "행정구역 코드·명칭 변경(통·폐합)은 v1에서 완전 remap 하지 않습니다 — 장기추세·과거 연도 해석 시 주의.",
    ],
    interpretation_hints: [],
    presets: [
      {
        id: "cancel",
        question: "해제 신고란?",
        answer:
          "국토부 공개 데이터에 「해제」로 표시된 거래입니다. 동일 물건의 정상 신고가 함께 있으면 정상 신고는 유지하고, 해제 행만 통계에서 뺍니다.",
      },
      {
        id: "dedupe",
        question: "중복은 어떻게 판단하나요?",
        answer:
          "법정동·지번·계약일·면적·금액 등을 조합한 transaction_hash 가 같으면 동일 거래의 반복 신고로 보고, 계약일·id 기준 최신 1건만 남깁니다.",
      },
    ],
  };
}

export interface FreeStatsExplainContext {
  data: FreeStatsV2Response;
  viewMode: "free" | "paid";
  isPaidBasic: boolean;
  windowYears: 3 | 5;
  useUpper: boolean;
  upperLevelLabel?: string;
}

export function buildFreeStatsExplain(ctx: FreeStatsExplainContext): AnalysisExplain {
  const asOf = statsAsOfLabel(ctx.data) ?? "—";
  const modeLabel =
    ctx.viewMode === "free"
      ? "무료 통계"
      : ctx.isPaidBasic
        ? "유료 · 기본 통계 보기"
        : "유료 통계";
  const period = `${ctx.data.period_start?.slice(0, 10) ?? "?"} ~ ${ctx.data.period_end?.slice(0, 10) ?? "?"}`;

  const hints = [
    `기준: ${asOf}`,
    `롤링 창: 최근 ${ctx.windowYears}년 (contract_date 기준)`,
    `집계 구간: ${period}`,
    `표본: ${ctx.data.total.count.toLocaleString("ko-KR")}건`,
  ];
  if (ctx.useUpper && ctx.upperLevelLabel) {
    hints.push(`상위 행정 집계: ${ctx.upperLevelLabel} (산하 법정동·리 합산)`);
  }

  return {
    spec_id: "land.free_stats_v2.v1",
    spec_version: "1.0",
    title: `${modeLabel} — 화면 구성`,
    summary:
      "선택 지역의 토지 실거래를 **직전 달 말 기준**으로 잡은 롤링 3·5년 창 안에서 요약합니다. " +
      "상단 연도별 표·범례·용도×지목 매트릭스는 **동일 표본·동일 기간**을 다른 각도로 보여 줍니다.",
    formula:
      "단가(만원/㎡) = 거래금액(만원) ÷ 계약면적(㎡)\n" +
      "매트릭스 셀 = 선택 구간 × 법정동·리 × 용도지역 × 지목 교차 표본",
    reference: "land_basic_stats_v2 또는 상위 land_upper_stats_v2 (as_of_month 스냅샷)",
    floor_groups: [
      "총거래 표(연도별): 달력 연도별 건수·총액·면적·가중 단가 + 연말 인구(별도 population_stats, 12월만)",
      "용도×지목 매트릭스: 각 셀 5행 — 거래수/최소 | 평균·25% | 중위 | 표준편차·75% | 95%신뢰구간·최대",
      "ALL×ALL 칸: 해당 지역 전체 용도·지목 합산 요약",
    ],
    controls: [
      "포함: is_valid, 해제 제외, 단가 산출 가능 거래",
      "미적용: 도로·면적구분·지분·IQR 등 유료 필터 (기본통계 단계)",
      "연말 인구: stats_month=12 인 population_stats 만 합산 (없는 연도는 빈 칸)",
    ],
    interpretation: [
      "「YYYY년 M월 말 기준」은 DB에 적재된 최신 V2 스냅샷(as_of_month)을 뜻합니다.",
      `롤링 ${ctx.windowYears}년 창은 기준일 직전 ${ctx.windowYears}년간 contract_date 가 걸친 거래입니다.`,
      "매트릭스에서 n≥15 건은 신뢰 구간(연한 강조), n<5 건은 흐리게 표시됩니다.",
      ctx.viewMode === "paid" && ctx.isPaidBasic
        ? "유료 기본통계 보기 후 「필터 분석 실행」을 누르면 연도·도로 등 고급 필터가 적용된 별도 결과로 이동합니다."
        : "유료 모드에서는 「필터 분석 실행」으로 고급 필터 결과를 볼 수 있습니다.",
    ],
    limitations: [
      "사전집계(V2)에 없는 법정코드는 합산에서 자동 제외될 수 있습니다(amber 안내).",
      "상위 행정(시·군·구 등)만 선택 시 법정동·리별 매트릭스가 아닌 상위 합산 통계입니다.",
    ],
    interpretation_hints: hints,
    presets: [
      {
        id: "vs-filter",
        question: "필터 분석과 무엇이 다른가요?",
        answer:
          "기본통계는 롤링 3·5년·필터 없음. 필터분석은 선택 연도 칩·도로·면적·이상치·지분 등을 적용한 live 집계입니다.",
      },
      {
        id: "year-table",
        question: "연도별 표의 연도는?",
        answer:
          "contract_date 가 속한 달력 연도입니다. 롤링 창 첫·끝 해는 1/1~12/31 전체가 아니라 창 경계에 맞게 잘릴 수 있습니다.",
      },
    ],
  };
}

export interface PaidFilteredExplainContext {
  result: PaidAnalysisResponse;
  regionLabel?: string;
}

export function buildPaidFilteredExplain(ctx: PaidFilteredExplainContext): AnalysisExplain {
  const req = ctx.result.request;
  const asOf = statsAsOfLabel(ctx.result) ?? "—";
  const years =
    req.years && req.years.length > 0
      ? req.years.slice().sort((a, b) => a - b).join(", ")
      : req.year_from != null && req.year_to != null
        ? `${req.year_from}~${req.year_to}`
        : "전체";

  const hints = [
    `기준: ${asOf}`,
    `선택 연도: ${years}`,
    `표본: ${ctx.result.total.count.toLocaleString("ko-KR")}건`,
    `이상치 제외: ${req.exclude_outlier ? `적용 (IQR×${req.outlier_iqr_multiplier})` : "안 함"}`,
    `지분거래: ${req.exclude_partial ? "제외" : "포함"}`,
  ];
  if (ctx.regionLabel) hints.push(`지역: ${ctx.regionLabel}`);

  return {
    spec_id: "land.paid_filtered.v1",
    spec_version: "1.0",
    title: "필터 분석 결과 — 화면 구성",
    summary:
      "좌측에서 고른 지역·연도·도로·면적·용도·지목·지분·이상치 조건을 **land_transactions 에 live 적용**한 표본으로 " +
      "용도×지목 매트릭스를 만듭니다. 기본통계 보기와 **기간 축·표본이 다를 수** 있습니다.",
    formula:
      "단가(만원/㎡) = 거래금액(만원) ÷ 계약면적(㎡)\n" +
      "매트릭스 = 필터 통과 거래만 zone_type × land_category 교차 집계",
    reference: "land_transactions (실시간 GROUP BY, base_cache_key 사용 시 기본통계 후보 고정)",
    floor_groups: [
      "상단(기본통계 보기): 롤링 3·5년 V2 사전집계 — 필터 없음",
      "필터 분석 결과: 선택 연도(만년력) + 고급 필터 적용 live 집계",
      "매트릭스 칸 클릭 → 연도별 추이·단가 분포·거래목록·장기추세 모달",
    ],
    controls: filterControlsList(req),
    interpretation: [
      "연도 칩은 contract_year(만년력) 기준입니다 — 기본통계의 롤링 contract_date 창과 다릅니다.",
      "200곳 초과·상위 단일 선택 등 일부 범위는 bulk API 대신 상위 사전집계·실시간 집계로 전환될 수 있습니다(amber 안내).",
      "매트릭스 칸을 클릭하면 해당 용도×지목에 한정된 상세 분석 모달이 열립니다.",
    ],
    limitations: [
      "필터 조합에 따라 표본이 매우 작아지면 단가·분위수가 불안정합니다(n<15 참고).",
      "base_cache_key 가 있으면 기본통계 후보 집합 안에서만 필터가 적용됩니다.",
    ],
    interpretation_hints: hints,
    presets: [
      {
        id: "outlier",
        question: "IQR 이상치 제외는?",
        answer:
          "선택한 용도×지목 칸(또는 전체 표본)의 단가 분포에서 Tukey 펜스(IQR×배수) 밖 값을 제외합니다. 거래목록·분포 탭에도 동일 정책이 적용됩니다.",
      },
    ],
  };
}

function filterControlsList(req: PaidAnalysisRequest): string[] {
  const items: string[] = [
    "포함: is_valid, 해제 제외, 단가 not null",
  ];
  if (req.road_conditions?.length) items.push(`도로: ${req.road_conditions.join(", ")}`);
  if (req.area_categories?.length) items.push(`면적구분: ${req.area_categories.join(", ")}`);
  if (req.area_sqm_min != null || req.area_sqm_max != null) {
    items.push(
      `면적(㎡): ${req.area_sqm_min ?? "—"} ~ ${req.area_sqm_max ?? "—"}`,
    );
  }
  if (req.zone_types?.length) items.push(`용도지역 필터: ${req.zone_types.join(", ")}`);
  if (req.land_categories?.length) items.push(`지목 필터: ${req.land_categories.join(", ")}`);
  return items;
}

export function buildMatrixLegendExplain(): AnalysisExplain {
  return {
    spec_id: "land.matrix_legend.v1",
    spec_version: "1.0",
    title: "용도×지목 매트릭스 — 셀 수치 의미",
    summary:
      "각 용도지역(행) × 지목(열) 교차 칸은 **5개 가격 통계 행**으로 구성됩니다. " +
      "왼쪽 열은 해당 칸 표본의 분포 요약, 오른쪽 열은 보조 분위·극값입니다.",
    formula: "단가(만원/㎡) = 거래금액(만원) ÷ 계약면적(㎡)",
    floor_groups: [
      "1행: 거래수(n) · 최소(min)",
      "2~3행: 평균(mean, 파란 굵게) · 25%분위(p25) / 중위(median, 굵게)",
      "4행: 표준편차(std) · 75%분위(p75)",
      "5행: 95% 신뢰구간(평균 t-구간) · 최대(max)",
    ],
    controls: [],
    interpretation: [
      "평균·중위·분위는 모두 **만원/㎡** 단위입니다.",
      "거래수 0이면 「—」 표시(0으로 두지 않음).",
      "n≥15: 신뢰 구간 강조(연한 녹색 배경), n<5: 흐린 표시.",
      "행·열 머리(용도지역·지목)의 건수·평균은 해당 축 **전체 합산**입니다.",
    ],
    limitations: [
      "극단값(대형 필지 등)은 평균을 끌어올릴 수 있어 중위·분위와 함께 보세요.",
      "95% 신뢰구간은 **평균** 기준이며 중위값 구간이 아닙니다.",
    ],
    interpretation_hints: [],
    presets: [
      {
        id: "mean-vs-median",
        question: "평균 vs 중위?",
        answer: "평균은 소수 고가 거래에 민감합니다. 중위(50%)는 대표값으로 더 안정적일 때가 많습니다.",
      },
      {
        id: "ci",
        question: "95% 신뢰구간은?",
        answer: "해당 칸 표본 평균 단가의 t-구간 추정치입니다. n이 작으면 구간이 넓어집니다.",
      },
    ],
  };
}

export function buildMatrixTableExplain(): AnalysisExplain {
  return {
    spec_id: "land.matrix_table.v1",
    spec_version: "1.0",
    title: "용도×지목 분석표 — 읽는 법",
    summary:
      "선택 지역·기간·필터 조건을 만족하는 거래를 용도지역(세로)과 지목(가로)으로 교차 집계한 표입니다. " +
      "범례(?)에서 각 수치의 의미를 확인할 수 있습니다.",
    interpretation: [
      "칸을 클릭하면(유료 필터분석) 해당 용도×지목의 연도별 추이·분포·거래목록·장기추세를 볼 수 있습니다.",
      "전체화면 버튼으로 넓게 볼 수 있습니다.",
      "「미지정」「기타」 칸은 원장에 용도·지목이 비어 있거나 축약 규칙에 해당하는 표본입니다.",
    ],
    limitations: [
      "ALL×ALL 은 전체 합산이며, 개별 칸 합과 일치하지 않을 수 있습니다(9조합 GROUPING SETS).",
    ],
    interpretation_hints: [],
    presets: [],
    controls: [],
    floor_groups: [],
  };
}

export interface TransactionListExplainContext {
  zoneType: string;
  landCategory: string;
  total?: number;
  excludeOutlier: boolean;
  outlierMultiplier: number;
  filterSummary?: string;
}

export function buildTransactionListExplain(
  ctx: TransactionListExplainContext,
): AnalysisExplain {
  const hints: string[] = [
    `용도×지목: ${ctx.zoneType} · ${ctx.landCategory}`,
    ctx.total != null ? `표본: ${ctx.total.toLocaleString("ko-KR")}건` : "",
    `이상치 제외: ${ctx.excludeOutlier ? `적용 (IQR×${ctx.outlierMultiplier})` : "안 함"}`,
  ].filter(Boolean);

  const pipeline = buildLedgerPipelineExplain();

  return {
    spec_id: "land.tx_list.v1",
    spec_version: "1.0",
    title: "거래 목록 — 데이터·산출 방법",
    summary:
      "필터분석(또는 매트릭스 칸)과 **동일 조건**을 land_transactions 에 적용한 뒤, " +
      "최신 계약 순으로 페이지 단위 조회합니다. CSV 내보내기는 동일 필터의 **전체 건**입니다.",
    formula: "단가(만원/㎡) = 거래금액(만원) ÷ 계약면적(㎡)",
    reference: "land_transactions + region_codes (beopjungri_name)",
    floor_groups: pipeline.floor_groups,
    controls: [
      ...(ctx.filterSummary ? [ctx.filterSummary] : []),
      "목록·CSV 공통: is_valid, 해제 제외, 단가 not null",
      ctx.excludeOutlier
        ? `이상치 제외: 해당 칸 단가 IQR×${ctx.outlierMultiplier} 밖 거래 제외`
        : "이상치 제외: 미적용",
    ],
    interpretation: [
      "계약일: contract_date 가 있으면 yyyy-MM-dd, 없으면 연·월(YYYY.MM) 표시.",
      "지번·지분·유형은 정제 단계에서 채운 표시 필드입니다(원본 지번 문자열).",
      "목록은 모달 필터와 동기화되며, 장기추세·기본통계 표본과 다를 수 있습니다.",
    ],
    limitations: pipeline.limitations,
    interpretation_hints: hints,
    presets: pipeline.presets,
  };
}

export function buildMatrixCellTrendExplain(isRolling: boolean): AnalysisExplain {
  return {
    spec_id: "land.matrix_cell_trend.v1",
    spec_version: "1.0",
    title: isRolling ? "롤링 구간별 추이" : "선택 연도별 추이",
    summary: isRolling
      ? "기본통계 롤링 창을 12개월 버킷으로 나눈 구간별 평균 단가·거래수 추이입니다."
      : "필터분석에서 선택한 **만년력 연도**별 평균 단가·거래수 추이입니다.",
    interpretation: [
      "파란 실선: 평균 단가(만원/㎡), 점선: 거래 건수.",
      "동일 필터·이상치 정책이 분포·거래목록 탭과 공유됩니다.",
    ],
    limitations: ["연도·구간에 거래가 없으면 점이 비어 있습니다."],
    interpretation_hints: [],
    presets: [],
    controls: [],
    floor_groups: [],
  };
}

export function buildHistogramExplain(): AnalysisExplain {
  return {
    spec_id: "land.matrix_histogram.v1",
    spec_version: "1.0",
    title: "단가 분포 히스토그램",
    summary:
      "선택한 표본 범위(전체 연도/특정 연·구간)에서 **만원/㎡** 단가의 빈도 분포입니다.",
    interpretation: [
      "가로축: 단가 구간, 세로축: 거래 건수.",
      "이상치 제외 옵션이 켜져 있으면 목록·추이와 동일하게 IQR 밖 값을 제외한 뒤 그립니다.",
    ],
    limitations: ["구간 경계는 자동 등분이며 소수 표본에서는 모양이 불안정할 수 있습니다."],
    interpretation_hints: [],
    presets: [],
    controls: [],
    floor_groups: [],
  };
}
