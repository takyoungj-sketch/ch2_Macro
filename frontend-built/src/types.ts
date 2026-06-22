export type AssetType = "commercial" | "factory" | "detached" | "all";
export type ResponseScale = "linear" | "log";

export interface BuiltTransactionRow {
  id: number;
  asset_type: string;
  addr1?: string | null;
  addr2?: string | null;
  addr3?: string | null;
  addr4?: string | null;
  addr5?: string | null;
  lot_number?: string | null;
  display_address?: string | null;
  road_name?: string | null;
  road_width_label?: string | null;
  deal_type?: string | null;
  trade_year_label?: string | null;
  contract_year?: number | null;
  contract_month?: number | null;
  contract_date?: string | null;
  zone_type?: string | null;
  building_use?: string | null;
  building_scale?: number | null;
  land_scale?: number | null;
  age_bucket?: number | null;
  price: number;
  gross_area?: number | null;
  land_area?: number | null;
  building_age?: number | null;
  road_code?: number | null;
}

export interface BuiltTransactionListResponse {
  total: number;
  page: number;
  page_size: number;
  items: BuiltTransactionRow[];
}

export interface BuiltFilterMeta {
  asset_types: string[];
  contract_years: number[];
  zone_types: string[];
  building_uses: string[];
  road_width_labels: string[];
  addr1_list: string[];
  as_of_month?: string | null;
  default_window_years: number;
}

export interface RegressionVariableSpec {
  gross_area: boolean;
  land_area: boolean;
  building_age: boolean;
  road_width_dummy: boolean;
  road_code: boolean;
  zone_type_dummy: boolean;
  building_use_dummy: boolean;
  asset_type_dummy: boolean;
  region_leaf_dummy: boolean;
}

export interface Addr3Option {
  name: string;
  count: number;
  disabled?: boolean;
  min_reliable_count?: number;
}

export interface RegionStructure {
  has_intermediate: boolean;
  intermediate_label?: string | null;
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

export interface RiPick {
  eup: string;
  ri: string;
}

export type IqrMultiplier = 1.5 | 2 | 3;

export interface RegressionRunRequest {
  asset_type: AssetType;
  addr1?: string;
  addr2?: string;
  addr3?: string;
  addr3_list?: string[];
  addr4_list?: string[];
  ri_list?: RiPick[];
  contract_year_from?: number;
  contract_year_to?: number;
  as_of_month?: string;
  window_years?: number;
  zone_types?: string[];
  building_uses?: string[];
  road_width_labels?: string[];
  gross_area_min?: number;
  gross_area_max?: number;
  land_area_min?: number;
  land_area_max?: number;
  building_age_min?: number;
  building_age_max?: number;
  road_code_min?: number;
  road_code_max?: number;
  variables: RegressionVariableSpec;
  response_scale?: ResponseScale;
  compare_admin_levels?: boolean;
  leaf_level?: "addr3" | "addr4";
  exclude_outliers_iqr: boolean;
  outlier_iqr_multiplier?: number;
}

export interface ScopeSampleFilterResponse {
  total: number;
  zone_types: { name: string; count: number }[];
  building_uses: { name: string; count: number }[];
  road_width_labels: { name: string; count: number }[];
  continuous: { name: string; min?: number | null; max?: number | null }[];
}

export interface SampleFilterState {
  zoneTypes: string[];
  buildingUses: string[];
  roadWidthLabels: string[];
  gross_area_min: string;
  gross_area_max: string;
  land_area_min: string;
  land_area_max: string;
  building_age_min: string;
  building_age_max: string;
}

export const EMPTY_SAMPLE_FILTER: SampleFilterState = {
  zoneTypes: [],
  buildingUses: [],
  roadWidthLabels: [],
  gross_area_min: "",
  gross_area_max: "",
  land_area_min: "",
  land_area_max: "",
  building_age_min: "",
  building_age_max: "",
};

export interface RegressionCoeff {
  name: string;
  estimate: number;
  std_err?: number | null;
  t_value?: number | null;
  p_value?: number | null;
}

export interface VifEntry {
  name: string;
  vif?: number | null;
}

export interface PredictOptions {
  zone_types: string[];
  building_uses: string[];
  road_width_labels: string[];
  asset_types: string[];
  zone_reference?: string | null;
  building_use_reference?: string | null;
  road_width_reference?: string | null;
  asset_type_reference?: string | null;
  region_leaves?: string[];
  region_reference?: string | null;
  continuous: { name: string; min?: number | null; max?: number | null }[];
}

export interface RegressionLevelResult {
  admin_level: "sigungu" | "gu" | "eupmyeondong" | "beopjungri";
  scope_label?: string | null;
  n: number;
  r_squared?: number | null;
  adj_r_squared?: number | null;
  f_statistic?: number | null;
  f_p_value?: number | null;
  significant_count: number;
  equation: string;
  coefficients: RegressionCoeff[];
  vif?: VifEntry[];
  vif_warning?: string | null;
  predict_options?: PredictOptions | null;
  warning?: string | null;
  mape?: number | null;
}

export interface CorrelationPoint {
  x: number;
  y: number;
}

export interface CorrelationSeries {
  variable: string;
  label: string;
  pearson_r?: number | null;
  points: CorrelationPoint[];
}

export interface RegressionRunResponse {
  primary: RegressionLevelResult;
  comparisons: RegressionLevelResult[];
  correlations: CorrelationSeries[];
  correlation_admin_level?: "sigungu" | "gu" | "eupmyeondong" | "beopjungri" | null;
  correlation_scope_label?: string | null;
  correlation_n?: number | null;
}

export interface RegressionPredictRequest extends RegressionRunRequest {
  admin_level: "sigungu" | "gu" | "eupmyeondong" | "beopjungri";
  gross_area?: number;
  land_area?: number;
  building_age?: number;
  road_code?: number;
  road_width_label?: string;
  zone_type?: string;
  building_use?: string;
  predict_asset_type?: string;
  region_leaf?: string;
}

export interface RegressionPredictResponse {
  admin_level: "sigungu" | "gu" | "eupmyeondong" | "beopjungri";
  scope_label?: string | null;
  n: number;
  y_hat: number;
  pi_lower: number;
  pi_upper: number;
  ci_lower: number;
  ci_upper: number;
  response_scale?: ResponseScale;
  warnings: string[];
}
