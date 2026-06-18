export type AssetType = "apartment" | "rowhouse" | "officetel" | "presale";
export type AssetSelectorType = AssetType | "all";
export type CommercialAssetType = "collective_shop" | "collective_factory";
export type AnyAssetType = AssetType | CommercialAssetType;

export function isCommercialAsset(t: AnyAssetType): t is CommercialAssetType {
  return t === "collective_shop" || t === "collective_factory";
}

export interface CollectiveFilterMeta {
  asset_types: string[];
  contract_years: number[];
  addr1_list: string[];
}

export interface RegionStructure {
  has_intermediate: boolean;
  intermediate_label: string | null;
  leaf_level: string;
  has_ri?: boolean;
  tx_count?: number;
}

export interface RegionOption {
  name: string;
  count: number;
  parent?: string | null;
  disabled?: boolean;
  min_reliable_count?: number;
}

export interface AnalysisFeatures {
  floor_index: boolean;
  regression: boolean;
  count_total: number;
  count_recent: number;
  messages: string[];
}

export interface BuildingStatsRow {
  building_key: string;
  display_name: string;
  /** @deprecated 목록은 jibun_address / road_address 사용 */
  address: string;
  jibun_address?: string;
  road_address?: string;
  building_year?: number | null;
  asset_type: string;
  count: number;
  mean?: number | null;
  median?: number | null;
  ci_lower?: number | null;
  ci_upper?: number | null;
  is_reliable: boolean;
  analysis?: AnalysisFeatures;
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

export interface FloorIndexCell {
  label: string;
  floor?: number | null;
  dong?: string | null;
  area?: number | null;
  count: number;
  mean_unit_price?: number | null;
  index?: number | null;
  is_reliable: boolean;
  is_reference?: boolean;
  gamma?: number | null;
  p_value?: number | null;
  index_lo?: number | null;
  index_hi?: number | null;
}

export interface FloorIndexResponse {
  building_key: string;
  display_name: string;
  asset_type: string;
  dimension: string;
  method?: string;
  reference_floor?: string | null;
  controls?: string[];
  n_total: number;
  n_regression?: number | null;
  r_squared?: number | null;
  baseline_median?: number | null;
  cells: FloorIndexCell[];
  warnings?: string[];
  explain?: AnalysisExplain | null;
  analysis?: AnalysisFeatures;
}

export interface CohortBuildingSummary {
  building_key: string;
  display_name: string;
  count: number;
}

export interface CohortFloorIndexResponse extends Omit<FloorIndexResponse, "building_key" | "display_name"> {
  building_keys: string[];
  cohort_buildings: CohortBuildingSummary[];
}

export interface BuildingListResponse {
  total: number;
  items: BuildingStatsRow[];
  data_source?: "mart" | "live";
  as_of_month?: string | null;
  stats_reference_date?: string | null;
  stats_as_of_label?: string | null;
  window_years?: number | null;
  period_start?: string | null;
  period_end?: string | null;
}

export interface CommercialFilterMeta {
  asset_types: string[];
  contract_years: number[];
  addr1_list: string[];
}

export interface CommercialClusterRow {
  cluster_key: string;
  display_label: string;
  asset_type: string;
  road_name?: string | null;
  addr3?: string | null;
  addr4?: string | null;
  resolution_mode?: string | null;
  zone_type?: string | null;
  building_use?: string | null;
  building_year?: number | null;
  area_bucket_label?: string | null;
  confidence_tier?: string | null;
  count: number;
  mean?: number | null;
  median?: number | null;
  ci_lower?: number | null;
  ci_upper?: number | null;
  is_reliable: boolean;
}

export interface CommercialAddressRow {
  lot_number: string;
  addr3?: string | null;
  addr4?: string | null;
  count: number;
  mean?: number | null;
  median?: number | null;
  ci_lower?: number | null;
  ci_upper?: number | null;
  is_reliable: boolean;
}

export interface CommercialAddressListResponse {
  cluster_key: string;
  road_name?: string | null;
  total: number;
  items: CommercialAddressRow[];
}

export interface CommercialClusterListResponse {
  total: number;
  items: CommercialClusterRow[];
}

export interface CommercialTransactionRow {
  id: number;
  asset_type: string;
  cluster_key: string;
  addr3?: string | null;
  addr4?: string | null;
  lot_number?: string | null;
  contract_year?: number | null;
  contract_month?: number | null;
  price: number;
  gross_area?: number | null;
  land_area?: number | null;
  unit_price?: number | null;
  floor?: number | null;
  building_year?: number | null;
  building_age?: number | null;
  zone_type?: string | null;
  building_use?: string | null;
  area_bucket_label?: string | null;
  road_name?: string | null;
  road_code?: number | null;
  road_width_label?: string | null;
}

export interface CommercialTransactionListResponse {
  total: number;
  items: CommercialTransactionRow[];
}

export interface CommercialYearlyStatsResponse {
  cluster_key: string;
  display_label: string;
  points: YearlyStatPoint[];
}

export interface CommercialHistogramResponse {
  cluster_key: string;
  bins: HistogramBin[];
  n: number;
  contract_year?: number | null;
  unit?: string;
}

export interface CommercialFloorIndexResponse {
  cluster_key: string;
  display_label: string;
  asset_type: string;
  dimension: string;
  method?: string;
  reference_floor?: string | null;
  controls?: string[];
  n_total: number;
  n_regression?: number | null;
  r_squared?: number | null;
  baseline_median?: number | null;
  cells: FloorIndexCell[];
  warnings?: string[];
  explain?: AnalysisExplain | null;
  analysis?: AnalysisFeatures;
}

export interface CommercialRegressionResponse {
  cluster_key: string;
  display_label: string;
  n: number;
  r_squared?: number | null;
  adj_r_squared?: number | null;
  coefficients: RegressionCoeff[];
  warnings: string[];
  explain?: AnalysisExplain | null;
}

export interface CollectiveTransactionRow {
  id: number;
  asset_type?: string;
  building_key?: string;
  display_name?: string;
  contract_year?: number | null;
  contract_month?: number | null;
  contract_date?: string | null;
  exclusive_area?: number | null;
  land_area?: number | null;
  price: number;
  unit_price?: number | null;
  floor?: number | null;
  dong?: string | null;
  housing_subtype?: string | null;
  building_age?: number | null;
  buyer_type?: string | null;
  seller_type?: string | null;
  deal_type?: string | null;
  road_name?: string | null;
}

export interface RollingStatPoint {
  bucket_index: number;
  period_start: string;
  period_end: string;
  label: string;
  count: number;
  mean?: number | null;
}

export interface RollingStatsResponse {
  building_key: string;
  display_name: string;
  window_years: number;
  as_of_month?: string | null;
  stats_as_of_label?: string | null;
  points: RollingStatPoint[];
  data_source?: "mart" | "live";
}

export interface YearlyStatPoint {
  year: number;
  count: number;
  mean?: number | null;
}

export interface YearlyStatsResponse {
  building_key: string;
  display_name: string;
  points: YearlyStatPoint[];
  data_source?: "mart" | "live";
}

export interface HistogramBin {
  lo: number;
  hi: number;
  count: number;
}

export interface HistogramResponse {
  building_key: string;
  bins: HistogramBin[];
  n: number;
  contract_year?: number | null;
  unit: string;
}

export interface RegressionCoeff {
  name: string;
  label: string;
  coef: number;
  se?: number | null;
  t?: number | null;
  p?: number | null;
}

export interface ContinuousRange {
  name: string;
  min?: number | null;
  max?: number | null;
}

export interface BuildingFeOption {
  building_key: string;
  display_name: string;
  count: number;
  is_reference?: boolean;
  has_fe?: boolean;
}

export interface CollectivePredictOptions {
  exclusive_area?: ContinuousRange | null;
  building_age?: ContinuousRange | null;
  floor?: ContinuousRange | null;
  max_floor?: number | null;
  floor_mode?: string;
  dongs?: string[];
  dong_reference?: string | null;
  housing_subtypes?: string[];
  housing_subtype_reference?: string | null;
  buildings?: BuildingFeOption[];
}

export interface CollectiveRegressionPredictInputs {
  exclusive_area?: number | null;
  building_age?: number | null;
  floor?: number | null;
  dong?: string | null;
  housing_subtype?: string | null;
  building_key?: string | null;
}

export interface CollectiveRegressionPredictResponse {
  n: number;
  y_hat: number;
  pi_lower: number;
  pi_upper: number;
  ci_lower: number;
  ci_upper: number;
  unit_price_hat?: number | null;
  warnings: string[];
}

export interface CollectiveRegressionResponse {
  building_key: string;
  display_name: string;
  n: number;
  r_squared?: number | null;
  adj_r_squared?: number | null;
  coefficients: RegressionCoeff[];
  warnings: string[];
  predict_options?: CollectivePredictOptions | null;
  explain?: AnalysisExplain | null;
}

export interface CohortRegressionResponse extends CollectiveRegressionResponse {
  building_keys?: string[];
  cohort_buildings?: CohortBuildingSummary[];
}

export interface YearlyStatsSeries {
  building_key: string;
  display_name: string;
  points: YearlyStatPoint[];
  data_source?: "mart" | "live";
}

export interface CohortYearlyStatsResponse {
  building_keys: string[];
  series: YearlyStatsSeries[];
  data_source: "live";
}

export interface CohortHistogramResponse {
  building_keys: string[];
  bins: HistogramBin[];
  n: number;
  contract_year?: number | null;
  data_source: "live";
}

export interface CohortTransactionsResponse {
  building_keys: string[];
  total: number;
  items: CollectiveTransactionRow[];
  data_source: "live";
}

export const ASSET_LABELS: Record<AssetType, string> = {
  apartment: "아파트",
  rowhouse: "연립·다세대",
  officetel: "오피스텔",
  presale: "분양권",
};

export const ASSET_SELECTOR_LABELS: Record<AssetSelectorType, string> = {
  all: "통합",
  ...ASSET_LABELS,
};

export function assetTypeLabel(t: string | undefined | null): string {
  if (!t) return "—";
  return ASSET_LABELS[t as AssetType] ?? t;
}

export const COMMERCIAL_ASSET_LABELS: Record<CommercialAssetType, string> = {
  collective_shop: "집합상가",
  collective_factory: "집합공장",
};
