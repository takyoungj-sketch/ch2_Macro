export type AssetType = "apartment" | "rowhouse" | "officetel";

export interface CollectiveFilterMeta {
  asset_types: string[];
  contract_years: number[];
  addr1_list: string[];
}

export interface BuildingStatsRow {
  building_key: string;
  display_name: string;
  asset_type: string;
  count: number;
  mean?: number | null;
  median?: number | null;
  ci_lower?: number | null;
  ci_upper?: number | null;
  is_reliable: boolean;
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
