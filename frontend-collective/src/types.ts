export type AssetType = "apartment" | "rowhouse" | "officetel";

export interface CollectiveFilterMeta {
  asset_types: string[];
  contract_years: number[];
  addr1_list: string[];
}

export interface RegionStructure {
  has_intermediate: boolean;
  intermediate_label: string | null;
  leaf_level: string;
}

export interface RegionOption {
  name: string;
  count: number;
  parent?: string | null;
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
  address: string;
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

export interface FloorIndexCell {
  label: string;
  floor?: number | null;
  dong?: string | null;
  area?: number | null;
  count: number;
  mean_unit_price?: number | null;
  index?: number | null;
  is_reliable: boolean;
}

export interface FloorIndexResponse {
  building_key: string;
  display_name: string;
  asset_type: string;
  dimension: string;
  n_total: number;
  baseline_median?: number | null;
  cells: FloorIndexCell[];
  analysis?: AnalysisFeatures;
}

export interface BuildingListResponse {
  total: number;
  items: BuildingStatsRow[];
}

export interface CollectiveTransactionRow {
  id: number;
  contract_year?: number | null;
  contract_month?: number | null;
  exclusive_area?: number | null;
  price: number;
  unit_price?: number | null;
  floor?: number | null;
  dong?: string | null;
  building_age?: number | null;
}

export interface YearlyStatPoint {
  year: number;
  count: number;
  mean?: number | null;
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

export interface CollectiveRegressionResponse {
  building_key: string;
  display_name: string;
  n: number;
  r_squared?: number | null;
  adj_r_squared?: number | null;
  coefficients: RegressionCoeff[];
  warnings: string[];
}

export const ASSET_LABELS: Record<AssetType, string> = {
  apartment: "아파트",
  rowhouse: "연립·다세대",
  officetel: "오피스텔",
};
