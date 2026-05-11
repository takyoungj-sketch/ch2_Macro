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
}

export interface FreeStatsResponse {
  beopjungri_code: string;
  beopjungri_name: string;
  year_from: number;
  year_to: number;
  total: StatsResult;
  by_year: YearlyTradeStat[];
  by_zone: Record<string, StatsResult>;
  by_land_category: Record<string, StatsResult>;
  matrix: MatrixCell[];
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
  road_conditions?: string[] | null;
  area_categories?: string[] | null;
  land_categories?: string[] | null;
  zone_types?: string[] | null;
  exclude_partial: boolean;
  exclude_outlier: boolean;
}

export interface PaidAnalysisResponse {
  request: PaidAnalysisRequest;
  total: StatsResult;
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

export type ViewMode = "free" | "paid";
