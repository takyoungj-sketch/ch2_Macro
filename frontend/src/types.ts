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
  region_codes: string[];
  year_from?: number | null;
  year_to?: number | null;
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

export type ViewMode = "free" | "paid";
