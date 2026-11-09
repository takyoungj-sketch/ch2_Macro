import type { AiContextPayload } from "@ch2/ai-assistant/aiClient";
import type {
  LandRegressionPredictResponse,
  LandRegressionResponse,
  LongTermTrendResponse,
  MatrixCell,
  MatrixYearlyStat,
  PaidAnalysisRequest,
  RegionItem,
  StatsResult,
  YearlyTradeStat,
} from "../types";
import type { TierCodes } from "../utils/regionTier";

export function buildLandRegressionContext(
  regData: LandRegressionResponse,
  opts: {
    regionLabel: string;
    zoneType: string;
    landCategory: string;
    modelType: "log" | "linear";
  },
): AiContextPayload {
  return {
    app: "land",
    panel: "LandRegressionTab",
    purpose: "statistics",
    scope: { region_label: opts.regionLabel },
    facts: {
      ...regData,
      zone_type: opts.zoneType,
      land_category: opts.landCategory,
      model_type: opts.modelType,
    },
  };
}

export function buildLandScatterContext(
  regData: LandRegressionResponse,
  opts: {
    regionLabel: string;
    zoneType: string;
    landCategory: string;
    activeTab?: "raw" | "partial";
  },
): AiContextPayload {
  return {
    app: "land",
    panel: "LandRegressionTab",
    purpose: "statistics",
    scope: { region_label: opts.regionLabel },
    facts: {
      ...(regData as unknown as Record<string, unknown>),
      zone_type: opts.zoneType,
      land_category: opts.landCategory,
      scatter_tab: opts.activeTab ?? "raw",
      unit: "만원/㎡",
    },
  };
}

export function buildLandPredictionContext(
  predict: LandRegressionPredictResponse,
  opts: {
    regionLabel: string;
    regressionN: number;
    adjR2: number;
  },
): AiContextPayload {
  return {
    app: "land",
    panel: "LandPredict",
    purpose: "statistics",
    scope: { region_label: opts.regionLabel },
    facts: {
      ...predict,
      unit: "만원/㎡",
      regression_n: opts.regressionN,
      adj_r_squared: opts.adjR2,
    },
  };
}

export function buildLandMatrixTrendContext(
  rows: MatrixYearlyStat[],
  opts: {
    regionLabel: string;
    zoneType: string;
    landCategory: string;
    metric?: "mean" | "median";
    isRolling?: boolean;
    asOfMonth?: string | null;
    scope?: LandAiScopeInput;
  },
): AiContextPayload {
  return {
    app: "land",
    panel: "TrendCard",
    purpose: "market_analysis",
    scope: opts.scope
      ? buildLandAiScope({ ...opts.scope, regionLabel: opts.regionLabel })
      : { region_label: opts.regionLabel },
    facts: {
      rows: annotateLandTrendRows(rows, { isRolling: Boolean(opts.isRolling), asOfMonth: opts.asOfMonth }),
      trend_metric: opts.metric ?? "mean",
      period_kind: opts.isRolling ? "rolling" : "calendar",
      zone_type: opts.zoneType,
      land_category: opts.landCategory,
      reliable_min_n: LAND_RELIABLE_MIN_N,
    },
  };
}

export function buildLandLongTermContext(
  data: LongTermTrendResponse,
  opts: { regionLabel: string },
): AiContextPayload {
  return {
    app: "land",
    panel: "TrendCard",
    purpose: "market_analysis",
    scope: { region_label: opts.regionLabel },
    facts: data as unknown as Record<string, unknown>,
  };
}

function sortLabelsByCount(
  labels: string[],
  totals: Record<string, StatsResult>,
  fallbackCount: (label: string) => number,
): string[] {
  return [...labels].sort((a, b) => {
    const countDiff =
      (totals[b]?.count ?? fallbackCount(b)) -
      (totals[a]?.count ?? fallbackCount(a));
    return countDiff || a.localeCompare(b, "ko-KR");
  });
}

/** 표와 같이 거래수 순 행·열의 (1,1)칸. 비어 있으면 거래수 최대 칸. */
export function pickLandMatrixTopCell(
  matrix: MatrixCell[],
  byZone: Record<string, StatsResult> = {},
  byLandCategory: Record<string, StatsResult> = {},
): {
  zone_type: string;
  land_category: string;
  stats: StatsResult;
  is_top_left: boolean;
} | null {
  const cells = matrix.filter((cell) => cell.stats != null);
  if (cells.length === 0) return null;
  const zones = sortLabelsByCount(
    Array.from(new Set(cells.map((cell) => cell.zone_type))),
    byZone,
    (label) =>
      cells
        .filter((cell) => cell.zone_type === label)
        .reduce((sum, cell) => sum + (cell.stats?.count ?? 0), 0),
  );
  const cats = sortLabelsByCount(
    Array.from(new Set(cells.map((cell) => cell.land_category))),
    byLandCategory,
    (label) =>
      cells
        .filter((cell) => cell.land_category === label)
        .reduce((sum, cell) => sum + (cell.stats?.count ?? 0), 0),
  );
  const zone = zones[0];
  const cat = cats[0];
  const topLeft = cells.find(
    (cell) => cell.zone_type === zone && cell.land_category === cat,
  );
  if (topLeft?.stats && topLeft.stats.count > 0) {
    return {
      zone_type: topLeft.zone_type,
      land_category: topLeft.land_category,
      stats: topLeft.stats,
      is_top_left: true,
    };
  }
  const richest = [...cells].sort(
    (a, b) => (b.stats?.count ?? 0) - (a.stats?.count ?? 0),
  )[0];
  if (!richest?.stats || richest.stats.count <= 0) return null;
  return {
    zone_type: richest.zone_type,
    land_category: richest.land_category,
    stats: richest.stats,
    is_top_left: false,
  };
}

// ---------------------------------------------------------------------------
// 토지 매트릭스 화면 문맥 (2026-11-09 지시서 §5.1)
// 스크린샷이 아니라 구조화된 통계만 보낸다. 원시 거래 행은 보내지 않는다.
// ---------------------------------------------------------------------------

/** 소표본 기준. 매트릭스 표의 신뢰 표시와 같은 n≥15. */
export const LAND_RELIABLE_MIN_N = 15;
/** 매트릭스 칸 전송 상한. 초과분은 거래수 순으로 자르고 메타로 알린다. */
export const LAND_MATRIX_CELL_LIMIT = 120;
const REGION_CODE_LIMIT = 20;

export interface LandAiScopeInput {
  regionLabel: string;
  regionLevel?: string | null;
  regionCodes?: readonly string[] | null;
  /** 롤링: period_start/period_end/window_years · 만년력: years 또는 year_from/year_to */
  period?: Record<string, unknown>;
  filters?: Record<string, unknown>;
  asOfMonth?: string | null;
  statsReferenceDate?: string | null;
}

export function buildLandAiScope(input: LandAiScopeInput): AiContextPayload["scope"] {
  const codes = (input.regionCodes ?? []).map((code) => code.trim()).filter(Boolean);
  const scope: AiContextPayload["scope"] = {
    region_label: input.regionLabel.trim() || undefined,
    region_level: input.regionLevel ?? undefined,
    region_code_count: codes.length || undefined,
    period: input.period,
    filters: { ...(input.filters ?? {}) },
    as_of_month: input.asOfMonth ?? undefined,
    stats_reference_date: input.statsReferenceDate ?? undefined,
  };
  if (codes.length > 0 && codes.length <= REGION_CODE_LIMIT) scope.region_codes = codes;
  return scope;
}

/** "충청북도 단양군 영춘면" 형태. 같은 단계 복수 선택은 "선택 지역 N곳". */
export function landRegionFullLabel(
  tier: TierCodes,
  regions: readonly RegionItem[],
): { label: string; level: string | null } {
  const clean = (codes: readonly string[]) => codes.map((code) => code.trim()).filter(Boolean);
  const levels: Array<[string, string[], (row: RegionItem) => string, (row: RegionItem) => string[]]> = [
    ["beopjungri", clean(tier.beopjungri_codes), (r) => r.beopjungri_code,
      (r) => [r.sido_name, r.sigungu_name, r.eupmyeondong_name, r.beopjungri_name]],
    ["eupmyeondong", clean(tier.eupmyeondong_codes), (r) => r.eupmyeondong_code,
      (r) => [r.sido_name, r.sigungu_name, r.eupmyeondong_name]],
    ["sigungu", clean(tier.sigungu_codes), (r) => r.sigungu_code, (r) => [r.sido_name, r.sigungu_name]],
    ["sido", clean(tier.sido_codes), (r) => r.sido_code, (r) => [r.sido_name]],
  ];
  const total = levels.reduce((sum, [, codes]) => sum + codes.length, 0) + clean(tier.city_codes).length;
  if (total === 0) return { label: "", level: null };
  if (total > 1) return { label: `선택 지역 ${total}곳`, level: "multi" };
  for (const [level, codes, codeOf, parts] of levels) {
    if (codes.length !== 1) continue;
    const row = regions.find((item) => codeOf(item) === codes[0]);
    if (!row) return { label: "", level };
    const names = parts(row).map((name) => (name ?? "").trim()).filter(Boolean);
    // 리 없는 법정동은 읍면동 이름과 같다.
    return { label: names.filter((name, i) => name !== names[i - 1]).join(" "), level };
  }
  return { label: "", level: "city" };
}

/** 실행된 요청 본문에서 AI에 보일 필터만 꺼낸다. 화면의 현재 입력값이 아니다. */
export function landFiltersFromRequest(req: PaidAnalysisRequest | null | undefined): Record<string, unknown> {
  if (!req) return {};
  const list = (value: string[] | null | undefined) => (value && value.length > 0 ? value : undefined);
  return {
    road_conditions: list(req.road_conditions),
    area_categories: list(req.area_categories),
    area_sqm_min: req.area_sqm_min ?? undefined,
    area_sqm_max: req.area_sqm_max ?? undefined,
    zone_types: list(req.zone_types),
    land_categories: list(req.land_categories),
    exclude_partial: Boolean(req.exclude_partial),
    deal_types: list(req.deal_types),
    exclude_outlier: Boolean(req.exclude_outlier),
    outlier_iqr_multiplier: req.exclude_outlier ? req.outlier_iqr_multiplier : undefined,
    matrix_mode: req.matrix_mode ?? "category",
  };
}

export function landPeriodFromRequest(req: PaidAnalysisRequest | null | undefined): Record<string, unknown> {
  if (!req) return {};
  if (req.rolling_matrix_period_start && req.rolling_matrix_period_end) {
    return {
      kind: "rolling",
      period_start: req.rolling_matrix_period_start,
      period_end: req.rolling_matrix_period_end,
      window_years: req.rolling_bucket_count ?? undefined,
    };
  }
  if (req.years && req.years.length > 0) return { kind: "calendar", years: [...req.years].sort((a, b) => a - b) };
  if (req.year_from != null || req.year_to != null) {
    return { kind: "calendar", year_from: req.year_from ?? undefined, year_to: req.year_to ?? undefined };
  }
  return {};
}

function cellStats(stats: StatsResult) {
  return {
    count: stats.count,
    mean: stats.mean,
    median: stats.median,
    p25: stats.p25,
    p75: stats.p75,
    min: stats.min,
    max: stats.max,
    ci_lower: stats.ci_lower,
    ci_upper: stats.ci_upper,
    is_reliable: stats.count >= LAND_RELIABLE_MIN_N,
  };
}

function statsMap(totals: Record<string, StatsResult> | undefined) {
  return Object.entries(totals ?? {})
    .filter(([, stats]) => stats != null && stats.count > 0)
    .sort((a, b) => b[1].count - a[1].count)
    .map(([label, stats]) => ({ label, ...cellStats(stats) }));
}

export function buildLandMatrixContext(opts: {
  scope: LandAiScopeInput;
  resultKind: "basic" | "filtered";
  matrixMode?: "category" | "group";
  matrix: readonly MatrixCell[];
  byZone?: Record<string, StatsResult>;
  byLandCategory?: Record<string, StatsResult>;
  byYear?: readonly YearlyTradeStat[];
  total?: StatsResult | null;
  /** 필터 입력이 바뀌어 화면 결과가 마지막 실행 조건 기준일 때 */
  filtersChanged?: boolean;
}): AiContextPayload {
  const filled = opts.matrix
    .filter((cell) => cell.stats != null && cell.stats.count >= 1)
    .sort((a, b) => b.stats.count - a.stats.count);
  const cells = filled.slice(0, LAND_MATRIX_CELL_LIMIT).map((cell) => ({
    zone_type: cell.zone_type,
    land_category: cell.land_category,
    ...cellStats(cell.stats),
  }));
  return {
    app: "land",
    panel: "LandMatrix",
    purpose: "statistics",
    scope: buildLandAiScope({
      ...opts.scope,
      filters: { ...(opts.scope.filters ?? {}), matrix_mode: opts.matrixMode ?? "category" },
    }),
    facts: {
      result_kind: opts.resultKind,
      matrix_mode: opts.matrixMode ?? "category",
      land_axis: opts.matrixMode === "group" ? "지목군" : "지목",
      total: opts.total ? cellStats(opts.total) : null,
      cells,
      cell_count: filled.length,
      omitted_cells: Math.max(0, filled.length - cells.length),
      by_zone: statsMap(opts.byZone),
      by_land_category: statsMap(opts.byLandCategory),
      by_year: (opts.byYear ?? []).map((row) => ({
        year: row.year,
        count: row.count,
        unit_price_per_sqm: row.unit_price_per_sqm,
      })),
      filters_changed: Boolean(opts.filtersChanged),
      reliable_min_n: LAND_RELIABLE_MIN_N,
    },
  };
}

/**
 * 셀 모달 추이 행에 부분 연도·소표본 표시를 붙인다.
 * 만년력: 기준월(as_of_month)이 속한 해는 그 달까지만 집계된 부분 연도다.
 */
export function annotateLandTrendRows(
  rows: readonly MatrixYearlyStat[],
  opts: { isRolling: boolean; asOfMonth?: string | null },
) {
  const asOf = opts.asOfMonth && /^\d{4}-\d{2}/.test(opts.asOfMonth) ? opts.asOfMonth : null;
  const asOfYear = asOf ? Number(asOf.slice(0, 4)) : null;
  const asOfMonthNo = asOf ? Number(asOf.slice(5, 7)) : null;
  return rows.map((row) => {
    const partial = !opts.isRolling && asOfYear != null && row.year === asOfYear && (asOfMonthNo ?? 12) < 12;
    return {
      year: row.year ?? undefined,
      bucket_index: row.bucket_index ?? undefined,
      period_start: row.period_start ?? undefined,
      period_end: row.period_end ?? undefined,
      chart_label: row.chart_label ?? undefined,
      count: row.count,
      mean: row.mean_unit_price_per_sqm,
      median: row.median_unit_price_per_sqm ?? null,
      p25: row.p25_unit_price_per_sqm ?? null,
      p75: row.p75_unit_price_per_sqm ?? null,
      is_partial_period: partial,
      covered_months: partial ? asOfMonthNo : undefined,
      is_small_sample: row.count < LAND_RELIABLE_MIN_N,
    };
  });
}
