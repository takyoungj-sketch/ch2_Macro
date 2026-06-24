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
export type RegionLevel = "sido" | "sigungu" | "eupmyeondong" | "city";

export interface UpperStatsV2Response {
  region_level: RegionLevel;
  region_code: string;
  region_name: string;
  as_of_month: string;
  stats_reference_date: string;
  period_start: string;
  period_end: string;
  window_years: number;
  total: StatsResult;
  by_year: YearlyTradeStat[];
  by_zone: Record<string, StatsResult>;
  by_land_category: Record<string, StatsResult>;
  matrix: MatrixCell[];
  by_year_calendar_reference?: YearlyTradeStat[];
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
  /** 참고 만년력 연도별(1·1~12·31) 집계 — 연도 필터 칩과 독립 */
  by_year_calendar_reference?: YearlyTradeStat[];
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
  /** 매트릭스 셀 모달 롤링 트렌드 — 매트릭스 V2와 동일 contract_date 창이어야 함(ISO yyyy-mm-dd 권장) */
  rolling_matrix_period_start?: string | null;
  rolling_matrix_period_end?: string | null;
  rolling_bucket_count?: number | null;
  rolling_stats_reference_date?: string | null;
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
  /** 계약연도 모드 레거시 */
  year?: number | null;
  bucket_index?: number | null;
  period_start?: string | null;
  period_end?: string | null;
  chart_label?: string | null;
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

export interface LongTermRegionTarget {
  region_level: RegionLevel | "beopjungri";
  region_code: string;
}

export interface LongTermTrendRequest {
  region_codes?: string[];
  region_targets?: LongTermRegionTarget[];
  zone_type: string;
  land_category: string;
  year_from?: number | null;
  year_to?: number | null;
}

export interface LongTermTrendPoint {
  year: number;
  count: number;
  mean?: number | null;
  median?: number | null;
  reference_only?: boolean;
}

export interface LongTermTrendSeries {
  region_level: string;
  region_code: string;
  region_name: string;
  points: LongTermTrendPoint[];
}

export interface LongTermTrendResponse {
  zone_type: string;
  land_category: string;
  year_from: number;
  year_to: number;
  disclaimer: string;
  series: LongTermTrendSeries[];
}

export interface AnalysisExplainPreset {
  id: string;
  question: string;
  answer: string;
}

export interface AnalysisExplain {
  spec_id: string;
  spec_version: string;
  title: string;
  summary: string;
  formula?: string | null;
  index_rule?: string | null;
  reference?: string | null;
  floor_groups?: string[];
  controls?: string[];
  interpretation: string[];
  limitations: string[];
  interpretation_hints: string[];
  presets: AnalysisExplainPreset[];
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
  histogram_bucket_index?: number | null;
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
  histogram_bucket_index?: number | null;
  histogram_period_start?: string | null;
  histogram_period_end?: string | null;
  bins: HistogramBin[];
}

export interface MatrixCellTransactionItem {
  id: number;
  contract_year: number;
  contract_month: number;
  contract_date?: string | null;
  beopjungri_code: string;
  sigungu_name?: string | null;
  beopjungri_name?: string | null;
  lot_display?: string | null;
  partial_ownership_label?: string | null;
  deal_type?: string | null;
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

export type ViewMode = "free" | "paid" | "profile";

/** GET /regional-profile */
export interface RegionalProfileMeta {
  profile_version: string;
  as_of_month: string;
  window_years: number;
  region_level: RegionLevel;
  region_code: string;
  feature_count?: number | null;
  builder_version?: string | null;
  validation_status: string;
  computed_at?: string | null;
}

export interface RegionalProfileResponse {
  meta: RegionalProfileMeta;
  features: Record<string, number>;
}

/** GET /regional-profile/twins/{eupmyeondong_code} */
export interface ProfileTwinNeighborItem {
  rank: number;
  twin_eupmyeondong_code: string;
  twin_eupmyeondong_name: string;
  twin_sigungu_name: string;
  twin_sido_name: string;
  similarity_score: number;
  detail_scores: Record<string, unknown>;
}

export interface ProfileTwinNeighborsResponse {
  profile_version: string;
  window_years: number;
  algorithm_version?: number;
  scope?: string | null;
  as_of_month?: string | null;
  batch_key?: string | null;
  anchor_eupmyeondong_code: string;
  neighbors: ProfileTwinNeighborItem[];
}

/** GET /regional-profile/twins-sigungu/{sigungu_code} — hybrid v7 */
export interface ProfileSigunguTwinItem {
  rank: number;
  twin_sigungu_code: string;
  twin_sigungu_name: string;
  twin_sido_name: string;
  similarity_score: number;
  detail_scores: Record<string, unknown>;
}

export interface ProfileSigunguTwinsResponse {
  profile_version: string;
  window_years: number;
  scope?: string | null;
  batch_key?: string | null;
  anchor_sigungu_code: string;
  neighbors: ProfileSigunguTwinItem[];
}

/** GET /twin-regions/latest-batch */
export interface TwinRegionLatestBatch {
  batch_key: string;
  computed_at: string | null;
  algorithm_version: number;
  sido_scope_codes: string;
  twin_row_count: number;
}

/** GET /twin-regions/neighbors/{sigungu_code} */
export interface TwinNeighborItem {
  rank: number;
  twin_sigungu_code: string;
  twin_sigungu_name: string;
  twin_sido_code: string;
  twin_sido_name: string;
  similarity_score: number;
  detail_scores: Record<string, unknown>;
}

export interface TwinNeighborsForSigunguResponse {
  batch_key: string;
  computed_at: string | null;
  algorithm_version: number;
  sido_scope_codes: string;
  anchor_sigungu_code: string;
  anchor_sigungu_name: string;
  anchor_sido_code: string;
  anchor_sido_name: string;
  neighbors: TwinNeighborItem[];
}

/** GET /twin-regions/eupmyeondong/neighbors/{code} */
export interface TwinEupmyeondongNeighborItem {
  rank: number;
  twin_eupmyeondong_code: string;
  twin_eupmyeondong_name: string;
  twin_sigungu_code: string;
  twin_sigungu_name: string;
  twin_sido_code: string;
  twin_sido_name: string;
  similarity_score: number;
  detail_scores: Record<string, unknown>;
}

export interface TwinNeighborsForEupmyeondongResponse {
  batch_key: string;
  computed_at: string | null;
  algorithm_version: number;
  sido_scope_codes: string;
  anchor_eupmyeondong_code: string;
  anchor_eupmyeondong_name: string;
  anchor_sigungu_code: string;
  anchor_sigungu_name: string;
  anchor_sido_code: string;
  anchor_sido_name: string;
  neighbors: TwinEupmyeondongNeighborItem[];
}

/** 로컬 UI: 현재 선택이 단일 읍면동으로 귀결될 때 */
export interface TwinEupAnchor {
  eupmyeondong_code: string;
  eupmyeondong_name: string;
  sigungu_code: string;
  sigungu_name: string;
  sido_code: string;
  sido_name: string;
}

/** 로컬 UI: 동일 시군구로만 귀결될 때(시·구 전체 등) 시군구 트윈 조회용 */
export interface TwinSigunguAnchor {
  sigungu_code: string;
  sigungu_name: string;
  sido_code: string;
  sido_name: string;
}

/** 쌍둥이 모달: 읍면동(인접 시도 후보) 또는 시군구(전국 후보) */
export type TwinCitySearchTarget =
  | { kind: "eupmyeondong"; anchor: TwinEupAnchor }
  | { kind: "sigungu"; anchor: TwinSigunguAnchor };

/** Twin v8 API region_level */
export type TwinV8RegionLevel = "sigungu" | "eupmyeondong" | "beopjungri";

/** GET /twin-v8/neighbors/{level}/{code} */
export interface TwinV8NeighborItem {
  rank: number;
  twin_region_code: string;
  twin_region_name: string;
  twin_sigungu_code: string | null;
  twin_sigungu_name: string | null;
  twin_sido_code: string;
  twin_sido_name: string;
  similarity_score: number;
  confidence_score: number;
  explanation_ko: string | null;
  detail_scores: Record<string, unknown>;
}

export interface TwinV8NeighborsResponse {
  batch_key: string;
  scope_label: string;
  region_level: TwinV8RegionLevel;
  anchor_region_code: string;
  anchor_region_name: string;
  algorithm_version: number;
  neighbors: TwinV8NeighborItem[];
}

/** UI: v8 조회 앵커 (충청권 sigungu/eup/beopjungri) */
export interface TwinV8Query {
  region_level: TwinV8RegionLevel;
  region_code: string;
  region_name: string;
  sido_code: string;
  sido_name: string;
  sigungu_name: string;
}
