import { api } from "./client";

export type RegionalRegressionVariables = {
  households: boolean;
  max_floor: boolean;
  building_age: boolean;
  parking: boolean;
  structure: boolean;
  builder: boolean;
  asset_type_dummy: boolean;
  assessed_land_price: boolean;
};

export type RegionalRegressionRunRequest = {
  addr1: string;
  addr2: string;
  addr3_list?: string[];
  addr4_list?: string[];
  window_years: number;
  asset_type?: string;
  variables: RegionalRegressionVariables;
  model_type: "linear" | "log";
  weight_mode: "equal" | "tx";
};

export type RegionalRegressionPredictInputs = {
  households?: number | null;
  max_floor?: number | null;
  building_age?: number | null;
  parking_per_household?: number | null;
  structure_group?: string | null;
  builder_group?: string | null;
  asset_type?: string | null;
  assessed_land_price?: number | null;
};

export type FunnelReason = {
  code: string;
  label: string;
  n: number;
};

export type FunnelStep = {
  code: string;
  label: string;
  n: number;
  delta?: number | null;
  kind: "remain" | "drop" | "split";
  note?: string | null;
  reasons: FunnelReason[];
};

export type SampleBreakdown = {
  n_pool: number;
  n_with_attributes: number;
  n_usable_tier: number;
  n_analysis?: number;
  n_fit: number;
  n_hold: number;
  n_missing_attr: number;
  n_weak_tier: number;
  n_no_price: number;
  funnel?: FunnelStep[];
};

export type BlockContribution = {
  block: string;
  label: string;
  weak: boolean;
  hold_mape?: number | null;
  in_sample_mape?: number | null;
  delta_mape_vs_core?: number | null;
  note?: string | null;
};

export type FittedBuildingRow = {
  building_key: string;
  display_name: string;
  y: number;
  y_hat: number;
  ape?: number | null;
  asset_type?: string | null;
  assessed_land_price?: number | null;
};

export type RegionalRegressionRunResponse = {
  n: number;
  model_type: "linear" | "log";
  weight_mode?: "equal" | "tx";
  n_effective?: number | null;
  r_squared?: number | null;
  adj_r_squared?: number | null;
  mape?: number | null;
  hold_mape?: number | null;
  rmse?: number | null;
  f_p_value?: number | null;
  equation?: string | null;
  coefficients: Array<{
    name: string;
    label: string;
    coef: number;
    se?: number | null;
    t?: number | null;
    p?: number | null;
    effect_plain?: string | null;
  }>;
  warnings: string[];
  sample: SampleBreakdown;
  blocks: BlockContribution[];
  fitted: FittedBuildingRow[];
  predict_options: Record<string, string[]>;
  reference_categories?: Record<string, string>;
  as_of_month?: string | null;
  snapshot_ym?: string | null;
  scope_label?: string | null;
};

export type RegionalRegressionPredictResponse = {
  n: number;
  model_type: "linear" | "log";
  weight_mode?: "equal" | "tx";
  y_hat: number;
  unit: string;
  warnings: string[];
  contributions: Array<{
    name: string;
    label: string;
    value: number;
    coef: number;
    product: number;
  }>;
};

export async function runRegionalRegression(
  body: RegionalRegressionRunRequest,
): Promise<RegionalRegressionRunResponse> {
  const { data } = await api.post<RegionalRegressionRunResponse>(
    "/analysis/regional-regression/run",
    body,
  );
  return data;
}

export async function predictRegionalRegression(
  body: RegionalRegressionRunRequest & { inputs: RegionalRegressionPredictInputs },
): Promise<RegionalRegressionPredictResponse> {
  const { data } = await api.post<RegionalRegressionPredictResponse>(
    "/analysis/regional-regression/predict",
    body,
  );
  return data;
}
