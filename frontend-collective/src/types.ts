export type AssetType = "apartment" | "rowhouse" | "officetel" | "presale";
/** API: 단일 / "a,b" / "all" */
export type AssetSelectorType = AssetType | "all" | string;
export type CommercialAssetType = "collective_shop" | "collective_factory";
export type CommercialAssetSelectorType = CommercialAssetType | "all" | string;
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

export interface TypeSibling {
  asset_type: string;
  building_key: string;
  display_name: string;
  count: number;
  median?: number | null;
  mean?: number | null;
}

export interface BuildingStatsRow {
  building_key: string;
  display_name: string;
  /** @deprecated 목록은 jibun_address / road_address 사용 */
  address: string;
  jibun_address?: string;
  road_address?: string;
  building_year?: number | null;
  households?: number | null;
  households_flagged?: boolean;
  builder_label?: string | null;
  builder_is_joint?: boolean;
  match_tier?: string | null;
  match_rule?: string | null;
  assessed_land_price?: number | null;
  assessed_land_price_year?: number | null;
  asset_type: string;
  count: number;
  mean?: number | null;
  median?: number | null;
  ci_lower?: number | null;
  ci_upper?: number | null;
  is_reliable: boolean;
  analysis?: AnalysisFeatures;
  type_siblings?: TypeSibling[];
  scale_scope?: "complex" | null;
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
  floor_mode?: string | null;
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
  diagnostics?: FloorIndexDiagnostics | null;
}

export interface FloorIndexDiagnostics {
  max_vif?: number | null;
  max_vif_term?: string | null;
  condition_number?: number | null;
  vifs?: Record<string, number>;
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
  presale_stats_mode?: "lifetime" | "rolling" | null;
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
  data_source?: "mart" | "live";
  as_of_month?: string | null;
  stats_reference_date?: string | null;
  stats_as_of_label?: string | null;
  window_years?: number | null;
  period_start?: string | null;
  period_end?: string | null;
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
  contract_date?: string | null;
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
  data_source?: "mart" | "live";
}

export interface CommercialRollingStatPoint {
  bucket_index: number;
  period_start: string;
  period_end: string;
  label: string;
  count: number;
  mean?: number | null;
}

export interface CommercialRollingStatsResponse {
  cluster_key: string;
  display_label: string;
  window_years: number;
  as_of_month?: string | null;
  stats_as_of_label?: string | null;
  points: CommercialRollingStatPoint[];
  data_source?: "mart" | "live";
}

export interface CommercialCohortClusterSummary {
  cluster_key: string;
  display_label: string;
  count: number;
}

export interface CommercialCohortYearlySeries {
  cluster_key: string;
  display_label: string;
  points: YearlyStatPoint[];
  data_source?: "mart" | "live";
}

export interface CommercialCohortYearlyStatsResponse {
  cluster_keys: string[];
  series: CommercialCohortYearlySeries[];
  data_source: "live";
}

export interface CommercialCohortHistogramResponse {
  cluster_keys: string[];
  bins: HistogramBin[];
  n: number;
  contract_year?: number | null;
  data_source: "live";
}

export interface CommercialCohortTransactionsResponse {
  cluster_keys: string[];
  total: number;
  items: CommercialTransactionRow[];
  data_source: "live";
}

export interface CommercialCohortRegressionResponse extends CommercialRegressionResponse {
  cluster_keys?: string[];
  cohort_clusters?: CommercialCohortClusterSummary[];
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
  floor_mode?: string | null;
  reference_floor?: string | null;
  regression_reference_floor?: string | null;
  controls?: string[];
  n_total: number;
  n_regression?: number | null;
  r_squared?: number | null;
  baseline_median?: number | null;
  cells: FloorIndexCell[];
  warnings?: string[];
  explain?: AnalysisExplain | null;
  diagnostics?: FloorIndexDiagnostics | null;
  analysis?: AnalysisFeatures;
}

export interface CommercialRegressionResponse {
  cluster_key: string;
  display_label: string;
  n: number;
  model_type?: RegressionModelType;
  r_squared?: number | null;
  adj_r_squared?: number | null;
  price_adj_r_squared?: number | null;
  mape?: number | null;
  f_p_value?: number | null;
  significant_count?: number;
  equation?: string;
  coefficients: RegressionCoeff[];
  warnings: string[];
  predict_options?: CommercialPredictOptions | null;
  model_comparison?: ModelComparison | null;
  explain?: AnalysisExplain | null;
}

export interface CommercialPredictOptions {
  gross_area?: ContinuousRange | null;
  building_age?: ContinuousRange | null;
  floor?: ContinuousRange | null;
  max_floor?: number | null;
  floor_mode?: string;
  road_code?: ContinuousRange | null;
  zone_types?: string[];
  zone_type_reference?: string | null;
  building_uses?: string[];
  building_use_reference?: string | null;
  road_width_labels?: string[];
  road_width_reference?: string | null;
}

export interface CommercialRegressionPredictInputs {
  gross_area?: number | null;
  building_age?: number | null;
  floor?: number | null;
  road_code?: number | null;
  zone_type?: string | null;
  building_use?: string | null;
  road_width_label?: string | null;
}

export interface CommercialRegressionPredictResponse {
  n: number;
  model_type?: RegressionModelType;
  y_hat: number;
  pi_lower: number;
  pi_upper: number;
  ci_lower: number;
  ci_upper: number;
  unit_price_hat?: number | null;
  warnings: string[];
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
  median?: number | null;
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
  effect_plain?: string | null;
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

export interface DongOption {
  dong: string;
  label: string;
  building_key?: string | null;
  is_reference?: boolean;
}

export interface CollectivePredictOptions {
  exclusive_area?: ContinuousRange | null;
  building_age?: ContinuousRange | null;
  floor?: ContinuousRange | null;
  max_floor?: number | null;
  floor_mode?: string;
  dongs?: string[];
  dong_reference?: string | null;
  dong_options?: DongOption[];
  housing_subtypes?: string[];
  housing_subtype_reference?: string | null;
  buildings?: BuildingFeOption[];
  households?: ContinuousRange | null;
  parking_per_household?: ContinuousRange | null;
  assessed_land_price?: ContinuousRange | null;
  structure_groups?: string[];
  structure_reference?: string | null;
  asset_types?: string[];
  asset_type_reference?: string | null;
}

export interface CollectiveRegressionPredictInputs {
  exclusive_area?: number | null;
  building_age?: number | null;
  floor?: number | null;
  dong?: string | null;
  housing_subtype?: string | null;
  building_key?: string | null;
  households?: number | null;
  parking_per_household?: number | null;
  assessed_land_price?: number | null;
  structure_group?: string | null;
  asset_type?: string | null;
}

export type RegressionModelType = "log" | "linear";

export interface CollectiveRegressionPredictResponse {
  n: number;
  model_type?: RegressionModelType;
  y_hat: number;
  pi_lower: number;
  pi_upper: number;
  ci_lower: number;
  ci_upper: number;
  unit_price_hat?: number | null;
  warnings: string[];
}

export interface ModelMetrics {
  model_type: RegressionModelType;
  adj_r_squared?: number | null;
  mape?: number | null;
  rmse?: number | null;
  cv_mape?: number | null;
  cv_folds?: number;
  cv_method?: string | null;
}

export interface CollectiveRegressionSpec {
  exclusive_area: boolean;
  building_age: boolean;
  floor: boolean;
  dong: boolean;
  housing_subtype: boolean;
  floor_mode: string;
  households?: boolean;
  parking?: boolean;
  assessed_land_price?: boolean;
  structure?: boolean;
  asset_type_dummy?: boolean;
}

export interface CollectiveModelCandidate {
  rank: number;
  blocks: string[];
  variables: CollectiveRegressionSpec;
  model_type: RegressionModelType;
  n: number;
  adj_r_squared?: number | null;
  mape?: number | null;
  cv_mape?: number | null;
}

export interface ModelComparison {
  log?: ModelMetrics | null;
  linear?: ModelMetrics | null;
  recommended: RegressionModelType;
  metric_basis: "cv" | "insample";
  confidence_stars: number;
  confidence_label?: string | null;
}

export interface CollectiveRegressionResponse {
  building_key: string;
  display_name: string;
  n: number;
  model_type?: RegressionModelType;
  r_squared?: number | null;
  adj_r_squared?: number | null;
  price_adj_r_squared?: number | null;
  mape?: number | null;
  f_p_value?: number | null;
  significant_count?: number;
  equation?: string;
  coefficients: RegressionCoeff[];
  warnings: string[];
  predict_options?: CollectivePredictOptions | null;
  model_comparison?: ModelComparison | null;
  model_candidates?: CollectiveModelCandidate[];
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

/** K-apt 단지 속성 (실험) — 값과 함께 출처·매칭 신뢰도·제외 사유를 받는다. */
export interface DanjiMatchInfo {
  tier: string;
  tier_label: string;
  rule: string;
  reliability: string;
  usable_for_regression: boolean;
  danji_code?: string | null;
  danji_name?: string | null;
  approved_year?: number | null;
  building_year?: number | null;
  year_diff?: number | null;
  note?: string | null;
  candidates?: DanjiMatchCandidate[];
}

export interface DanjiMatchCandidate {
  danji_code?: string | null;
  danji_name?: string | null;
  households?: number | null;
  builder_raw?: string | null;
}

export interface DanjiBuilderInfo {
  raw?: string | null;
  norm?: string | null;
  group?: string | null;
  is_joint: boolean;
  is_public: boolean;
  developer_raw?: string | null;
}

export interface DanjiBrandInfo {
  name?: string | null;
  confidence?: string | null;
  is_public: boolean;
  detected_from?: string | null;
}

export interface DanjiScaleInfo {
  households?: number | null;
  households_sale?: number | null;
  households_rent?: number | null;
  dong_count?: number | null;
  max_floor?: number | null;
  parking_total?: number | null;
  parking_per_household?: number | null;
}

export interface DanjiStructureInfo {
  raw?: string | null;
  group?: string | null;
}

export interface DanjiClassificationInfo {
  danji_class?: string | null;
  supply_type?: string | null;
}

export interface DanjiLandPriceInfo {
  assessed_land_price?: number | null;
  assessed_land_price_year?: number | null;
  representative_pnu?: string | null;
  source?: string | null;
}

export interface DanjiQualityFlag {
  code: string;
  label: string;
  detail?: string | null;
  affected_fields: string[];
}

export interface DanjiAttributesResponse {
  building_key: string;
  snapshot_ym?: string | null;
  source_label: string;
  dictionary_version?: string | null;
  matched: boolean;
  match: DanjiMatchInfo;
  builder?: DanjiBuilderInfo | null;
  brand?: DanjiBrandInfo | null;
  scale?: DanjiScaleInfo | null;
  structure?: DanjiStructureInfo | null;
  classification?: DanjiClassificationInfo | null;
  land_price?: DanjiLandPriceInfo | null;
  quality_flags: DanjiQualityFlag[];
  notes: string[];
}

export const ASSET_LABELS: Record<AssetType, string> = {
  apartment: "아파트",
  rowhouse: "연립·다세대",
  officetel: "오피스텔",
  presale: "분양권",
};

export const ASSET_SELECTOR_LABELS: Record<AssetType | "all", string> = {
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

export const COMMERCIAL_ASSET_SELECTOR_LABELS: Record<CommercialAssetType | "all", string> = {
  all: "통합",
  ...COMMERCIAL_ASSET_LABELS,
};

export function commercialAssetTypeLabel(t: string | undefined | null): string {
  if (!t) return "—";
  return COMMERCIAL_ASSET_LABELS[t as CommercialAssetType] ?? t;
}
