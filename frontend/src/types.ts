export interface StatsResult {
  count: number;
  mean: number | null;
  std?: number | null;
  ci_lower: number | null;
  ci_upper: number | null;
  min: number | null;
  p25: number | null;
  median: number | null;
  p75: number | null;
  max: number | null;
  is_reliable: boolean;
}

export interface MatrixCell {
  zone_type: string;
  land_category: string;
  stats: StatsResult;
}

export interface YearlyTradeStat {
  year: number;
  count: number;
  total_price_10k_sum: number;
  area_sqm_sum: number;
  unit_price_per_sqm: number | null;
  /** 해당 연도 연말 법정동 인구 합 (population_stats 없으면 null/미포함) */
  population_year_end?: number | null;
}

/**
 * 상위 행정구역 사전집계 (`/api/paid/upper-stats/{level}/{code}`).
 * 설계: docs/UPPER_STATS_DESIGN.md / DECISIONS D-009.
 */
export type RegionLevel = "sido" | "sigungu" | "eupmyeondong";

export interface UpperStatsV2Response {
  region_level: RegionLevel;
  region_code: string;
  region_name: string;
  as_of_month: string;
  stats_reference_date: string;
  period_start: string;
  period_end: string;
  window_years: number;
  zone_type: string;
  land_category: string;
  stats: StatsResult;
}

/** 무료 통계 V2 API (`/api/free/v2/…`) — 계약일(contract_date) 롤링 창 */
export type FreeStatsWindowYears = 3 | 5;

/** 쿼리/스토어 값이 비어 있거나 잘못돼도 API에는 3 또는 5만 보냄 (빈 window_years → 422 방지) */
export function normalizeFreeStatsWindowYears(v: unknown): FreeStatsWindowYears {
  if (v === 3 || v === "3") return 3;
  if (v === 5 || v === "5") return 5;
  return 5;
}

export interface FreeStatsV2Response {
  beopjungri_code: string;
  beopjungri_name: string;
  /** 기준 스냅샷 월(YYYY-MM-01) */
  as_of_month: string;
  /** UI 기준일: as_of_month 다음 달 1일. 구버전 API면 없을 수 있음 */
  stats_reference_date?: string;
  period_start: string;
  period_end: string;
  window_years: FreeStatsWindowYears;
  analysis_base_key?: string | null;
  total: StatsResult;
  by_year: YearlyTradeStat[];
  by_zone: Record<string, StatsResult>;
  by_land_category: Record<string, StatsResult>;
  matrix: MatrixCell[];
  stats_excluded_codes?: string[];
}

/** @deprecated 서버 V1 제거됨 — `FreeStatsV2Response` 사용 */
export type FreeStatsResponse = FreeStatsV2Response;

export type RegionScopeType = "beopjungri" | "eupmyeondong" | "sigungu";

export interface RegionSelectionUnit {
  scope_type: RegionScopeType;
  code: string;
}

export interface RegionItem {
  beopjungri_code: string;
  beopjungri_name: string;
  eupmyeondong_code: string;
  eupmyeondong_name: string;
  sigungu_code: string;
  sigungu_name: string;
  sido_code: string;
  sido_name: string;
}

export interface PaidAnalysisRequest {
  /** 복수 선택: 법정단위·읍면동·시군구 (하나 이상). legacy `region_codes` 대체 */
  region_selections?: RegionSelectionUnit[] | null;
  /** 레거시 법정동·리 코드 목록 (각각 beopjungri 로 처리) */
  region_codes?: string[] | null;

  year_from?: number | null;
  year_to?: number | null;
  /** 비연속 연도 선택 시 사용. 설정 시 서버에서 year_from/to 대신 적용 */
  years?: number[] | null;
  /** 기본 통계 보기에서 서버가 만든 후보 거래행 캐시 키 */
  base_cache_key?: string | null;
  road_conditions?: string[] | null;
  area_categories?: string[] | null;
  /** 계약면적(㎡) 하한·상한(포함). 둘 중 하나만 있어도 됨. 지정 시 광소/정상/광대(area_categories)는 서버에서 적용하지 않음(B 모드). */
  area_sqm_min?: number | null;
  area_sqm_max?: number | null;
  land_categories?: string[] | null;
  zone_types?: string[] | null;
  exclude_partial: boolean;
  exclude_outlier: boolean;
  /** 이상치 제외 시 단가 Tukey 펜스 IQR 배수 (1.5 / 2 / 3) */
  outlier_iqr_multiplier: number;
}

export interface PaidAnalysisResponse {
  request: PaidAnalysisRequest;
  total: StatsResult;
  /** 필터 적용 후 연도별 요약(상단 표); 없으면 기본통계 by_year 에서 선택 연도만 필터 */
  by_year?: YearlyTradeStat[];
  by_region: Record<string, StatsResult>;
  by_zone: Record<string, StatsResult>;
  by_land_category: Record<string, StatsResult>;
  by_road_condition: Record<string, StatsResult>;
  matrix: MatrixCell[];
  response_ms: number;
  /**
   * DECISIONS D-006 — V2 사전집계의 최신 스냅샷 월 1일. 무료/유료 화면이 같은 「YYYY년 M월 말 기준」 표기를 쓰도록 노출.
   * 비어 있으면 V2 사전집계가 적재되지 않은 상태.
   */
  as_of_month?: string | null;
  /** UI 표시용 기준일 — `as_of_month` 의 다음 달 1일. 화면 상단 라벨과 1:1. */
  stats_reference_date?: string | null;
}

export interface MatrixYearlyStat {
  year: number;
  count: number;
  mean_unit_price_per_sqm: number | null;
}

export interface MatrixYearlyRequest extends PaidAnalysisRequest {
  zone_type: string;
  land_category: string;
}

export interface MatrixYearlyResponse {
  zone_type: string;
  land_category: string;
  rows: MatrixYearlyStat[];
}

export interface HistogramBin {
  bin_from: number;
  bin_to: number;
  count: number;
}

/** POST /paid/matrix-cell-histogram 요청 (MatrixYearlyRequest + 분포 옵션) */
export interface MatrixCellHistogramRequest extends MatrixYearlyRequest {
  histogram_scope?: "all" | "single";
  histogram_year?: number | null;
  bin_count?: number;
}

export interface MatrixCellHistogramResponse {
  zone_type: string;
  land_category: string;
  n: number;
  exclude_outlier: boolean;
  outlier_iqr_multiplier: number;
  histogram_scope: "all" | "single";
  histogram_year?: number | null;
  bins: HistogramBin[];
}

export interface MatrixCellTransactionItem {
  id: number;
  contract_year: number;
  contract_month: number;
  beopjungri_code: string;
  beopjungri_name?: string | null;
  area_sqm?: number | null;
  total_price_10k: number;
  unit_price_per_sqm?: number | null;
  road_condition?: string | null;
}

/** POST /paid/matrix-cell-transactions 요청 */
export interface MatrixCellTransactionsRequest extends MatrixYearlyRequest {
  offset?: number;
  limit?: number;
}

export interface MatrixCellTransactionsResponse {
  zone_type: string;
  land_category: string;
  total: number;
  offset: number;
  limit: number;
  exclude_outlier: boolean;
  outlier_iqr_multiplier: number;
  items: MatrixCellTransactionItem[];
}

export type ViewMode = "free" | "paid";
