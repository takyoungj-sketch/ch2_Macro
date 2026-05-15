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

export interface FreeStatsResponse {
  beopjungri_code: string;
  beopjungri_name: string;
  year_from: number;
  year_to: number;
  analysis_base_key?: string | null;
  total: StatsResult;
  by_year: YearlyTradeStat[];
  by_zone: Record<string, StatsResult>;
  by_land_category: Record<string, StatsResult>;
  matrix: MatrixCell[];
  /** 합산 요청에 포함됐으나 사전집계 부재로 빠진 법정코드 */
  stats_excluded_codes?: string[];
}

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
