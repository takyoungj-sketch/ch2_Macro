export type RentAssetType = "apartment" | "rowhouse" | "officetel" | "detached";
export type StatsWindowYears = 3 | 5 | 7;

export type LeaseMetric = {
  n: number;
  mean: number | null;
  median: number | null;
  ci_lower: number | null;
  ci_upper: number | null;
};

export type MixedLeaseMetric = {
  n: number;
  deposit: LeaseMetric;
  monthly: LeaseMetric;
};

export type RentConversionRate = {
  asset_type: string;
  r_selected: number | null;
  method_selected: string;
  gate_passed: boolean;
  n_buildings: number;
  n_jeonse: number;
  n_mixed: number;
  r_mean_simple: number | null;
  r_mean_weighted: number | null;
  r_ols_origin: number | null;
  r_ols_weighted: number | null;
  scope?: string;
  addr3?: string;
  fallback?: boolean;
};

export type RentBuildingRow = {
  building_key: string;
  asset_type: RentAssetType | string;
  display_name: string;
  jibun_address: string;
  road_address: string;
  building_year: number | null;
  addr3?: string;
  jeonse: LeaseMetric;
  mixed: MixedLeaseMetric;
  monthly: LeaseMetric;
  jeonse_equiv: LeaseMetric;
  monthly_equiv: LeaseMetric;
  sale?: LeaseMetric;
  jeonse_to_sale_pct?: number | null;
  jeonse_equiv_sale_pct?: number | null;
};

export type RentBuildingListResponse = {
  items: RentBuildingRow[];
  total: number;
  as_of_month: string | null;
  window_years: number;
  period_start: string | null;
  period_end: string | null;
  stats_as_of_label: string;
  unit: string;
  conversion_rates: RentConversionRate[];
  conversion_applied: boolean;
  conversion_method: string;
  conversion_scope?: string;
  conversion_fallback?: boolean;
};

export type RentRollingPoint = {
  bucket_index: number;
  period_start: string;
  period_end: string;
  label: string;
  jeonse: LeaseMetric;
  mixed: MixedLeaseMetric;
  monthly: LeaseMetric;
};

export type RentConversionCompareRow = {
  addr1: string;
  addr2: string;
  asset_type: string;
  window_years: number;
  n_buildings: number;
  n_jeonse: number;
  n_mixed: number;
  r_mean_simple: number | null;
  r_mean_weighted: number | null;
  r_ols_origin: number | null;
  r_ols_weighted: number | null;
  r_selected: number | null;
  method_selected: string;
  gate_passed: boolean;
};

export type RentRegionOption = { name: string; count: number; parent?: string | null };

export type RentRegionStructure = {
  has_intermediate: boolean;
  intermediate_label: string | null;
  leaf_level: string;
};

export type ValidateMethodKey = "mean_simple" | "mean_weighted" | "ols_origin" | "ols_weighted";

export type ValidateMetrics = {
  cells: number;
  mae_median: number | null;
  mape_median: number | null;
  median_ae_median: number | null;
};

export type ValidateSplit = {
  summary: Record<ValidateMethodKey, ValidateMetrics>;
  n_cells: number;
};

export type RentConversionValidateReport = {
  as_of: string;
  addr1: string;
  windows: Record<
    string,
    {
      period: [string, string];
      in_sample_sigungu: ValidateSplit;
      in_sample_dong: ValidateSplit;
      holdout_sigungu: ValidateSplit;
      holdout_dong: ValidateSplit;
    }
  >;
};

export type RbBand = "stable" | "mild" | "unstable";

export type RbDistCell = {
  addr1: string;
  addr2: string;
  addr3: string;
  asset_type: string;
  window_years: number;
  level: "sigungu" | "dong";
  n: number;
  n_jeonse: number;
  n_mixed: number;
  mean: number;
  median: number;
  mad: number;
  min: number;
  max: number;
  mean_minus_median: number;
  band: RbBand;
};

export type RbBandTally = { n: number; pct: number };

export type RentRbDistributionReport = {
  as_of: string;
  addr1: string;
  n_cells: number;
  bands: Record<string, Record<RbBand, RbBandTally>>;
  cells: RbDistCell[];
};

export const CONVERSION_METHOD_LABELS: Record<string, string> = {
  r_mean_simple: "단순평균",
  r_mean_weighted: "n가중",
  r_ols_origin: "원점회귀",
  r_ols_weighted: "가중회귀",
};

export const RENT_ASSET_KINDS: RentAssetType[] = [
  "apartment",
  "rowhouse",
  "officetel",
  "detached",
];

export const RENT_KIND_LABELS: Record<RentAssetType, string> = {
  apartment: "아파트",
  rowhouse: "연립다세대",
  officetel: "오피스텔",
  detached: "단독다가구",
};

export function assetTypeLabel(t: string): string {
  return RENT_KIND_LABELS[t as RentAssetType] ?? t;
}

export type SangkwonAssetKind =
  | "office"
  | "mid_retail"
  | "small_retail"
  | "strata"
  | "retail_all";

export const SANGKWON_KINDS: SangkwonAssetKind[] = [
  "office",
  "mid_retail",
  "small_retail",
  "strata",
  "retail_all",
];

export const SANGKWON_KIND_LABELS: Record<SangkwonAssetKind, string> = {
  office: "오피스",
  mid_retail: "중대형 상가",
  small_retail: "소규모 상가",
  strata: "집합 상가",
  retail_all: "상가통합",
};

export const SANGKWON_METRIC_LABELS: Record<string, string> = {
  building_count: "동수·호수",
  avg_floors: "평균층수",
  avg_area: "평균면적(㎡)",
  rent: "임대료(만원/㎡·년)",
  rent_index: "임대가격지수",
  noi_per_m2: "순영업소득(만원/㎡·년)",
  rent_income_share: "임대수입(%)",
  other_income_share: "기타수입(%)",
  opex_share: "운영경비(%)",
  noi_pct: "순영업소득(%)",
  vacancy: "공실률(%)",
  income_yield: "소득수익률(%)",
  capital_yield: "자본수익률(%)",
  investment_yield: "투자수익률(%)",
  conversion: "전환율(%)",
  floor_rent: "층별임대료(만원/㎡·년)",
  floor_utility: "층별효용비율(%)",
};

export const SANGKWON_METRIC_HELP: Record<string, string> = {
  building_count: "sangkwon_building_count",
  avg_floors: "sangkwon_avg_floors",
  avg_area: "sangkwon_avg_area",
  rent: "sangkwon_rent",
  rent_index: "sangkwon_rent_index",
  noi_per_m2: "sangkwon_noi_per_m2",
  rent_income_share: "sangkwon_rent_income",
  other_income_share: "sangkwon_other_income",
  opex_share: "sangkwon_opex",
  noi_pct: "sangkwon_noi_pct",
  vacancy: "sangkwon_vacancy",
  income_yield: "sangkwon_income_yield",
  capital_yield: "sangkwon_capital_yield",
  investment_yield: "sangkwon_investment_yield",
  conversion: "sangkwon_conversion",
};

export type SangkwonHit = {
  sec_nm: string;
  sido: string;
  buld_nm: string;
  overlapScore: number;
};

export type SangkwonAnnualResponse = {
  year: number | null;
  sec_nm: string;
  sido: string;
  rows: {
    metric: string;
    group?: string;
    group_label?: string;
    values: Record<string, number | null>;
  }[];
  source_file: string;
  latest_year: number | null;
  latest_quarter: number | null;
  window_label?: string;
  window_mode?: string;
  window_start_year?: number | null;
  window_start_quarter?: number | null;
  window_end_year?: number | null;
  window_end_quarter?: number | null;
};

export type SangkwonSeriesResponse = {
  sec_nm: string;
  sido: string;
  from_year: number;
  years: number[];
  series: {
    asset_kind: string;
    metric: string;
    floor_label: string;
    points: { year: number; value: number | null }[];
  }[];
  floor_labels: string[];
  source_file: string;
  break_note: string;
};
