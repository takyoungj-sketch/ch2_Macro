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
  evaluation_region_addrs?: string[];
  addr1: string;
  addr2: string;
  addr3_list?: string[];
  addr4_list?: string[];
  region_codes?: string[];
  region_code_level?: string;
  region_addrs?: string[];
  window_years: number;
  asset_type?: string;
  variables: RegionalRegressionVariables;
  model_type: "linear" | "log";
  categorical_missing?: "keep_unknown" | "drop";
  weight_mode: "equal" | "tx";
  min_tx?: 2 | 3 | 5;
  region_dummy?: boolean;
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
  region_group?: string | null;
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
  transaction_n?: number | null;
  address?: string | null;
  building_key: string;
  display_name: string;
  y: number;
  y_hat: number;
  ape?: number | null;
  asset_type?: string | null;
  assessed_land_price?: number | null;
  households?: number | null;
  max_floor?: number | null;
  building_age?: number | null;
  parking_per_household?: number | null;
  structure_group?: string | null;
  builder_group?: string | null;
  region_group?: string | null;
};

export type NewBuildAge0Gap = {
  n_0_3: number;
  n_0_1: number;
  median_residual_pct?: number | null;
  mean_residual_pct?: number | null;
  underpred_share_pct?: number | null;
  thin: boolean;
};

export type RegionalRegressionRunResponse = {
  extension_comparison?: {
    status: "available" | "unavailable";
    reason?: string | null;
    evaluation_n: number;
    fit_before_n: number;
    fit_after_n: number;
    mape_before?: number | null;
    mape_after?: number | null;
    evaluation_signature?: string | null;
    role: "selection_validation";
  } | null;
  analysis?: import("../../../shared/regression-ui/types").RegressionAnalysisContext | null;
  model_adj_r_squared?: number | null;
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
  categorical_missing?: "keep_unknown" | "drop";
  n_excluded_missing?: number;
  missing_treatment_label?: string;
  sample: SampleBreakdown;
  blocks: BlockContribution[];
  fitted: FittedBuildingRow[];
  predict_options: Record<string, string[]>;
  reference_categories?: Record<string, string>;
  as_of_month?: string | null;
  snapshot_ym?: string | null;
  scope_label?: string | null;
  newbuild_age0_gap?: NewBuildAge0Gap | null;
  model_candidates?: Array<{
    validation?: import("../../../shared/regression-ui/types").RegressionValidationContext | null;
    comparison?: import("../../../shared/regression-ui/types").RegressionComparisonContext | null;
    rank: number;
    purpose?: "predictive" | "explanatory";
    blocks: string[];
    model_type: "linear" | "log";
    n: number;
    adj_r_squared?: number | null;
    mape?: number | null;
    hold_mape?: number | null;
  }>;
};

export type RegionalRegressionPredictResponse = {
  n: number;
  model_type: "linear" | "log";
  weight_mode?: "equal" | "tx";
  y_hat: number;
  unit: string;
  ci_lower?: number | null;
  ci_upper?: number | null;
  pi_lower?: number | null;
  pi_upper?: number | null;
  warnings: string[];
  contributions: Array<{
    name: string;
    label: string;
    value: number;
    coef: number;
    product: number;
  }>;
};

export type AptTwinPlace = {
  rank: number | null;
  label: string;
  addr1: string;
  addr2: string;
  addr4: string;
  region_addr: string;
  n_complexes: number;
};

export type AptTwinListResponse = {
  as_of_label: string;
  anchor: AptTwinPlace | null;
  twins: AptTwinPlace[];
  scope_anchors: AptTwinPlace[];
};

export async function fetchAptTwins(body: {
  addr1: string;
  addr2?: string;
  addr4?: string;
  region_code?: string;
}): Promise<AptTwinListResponse> {
  const { data } = await api.post<AptTwinListResponse>(
    "/analysis/regional-regression/apt-twins",
    body,
  );
  return data;
}

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
  body: RegionalRegressionRunRequest & { inputs: RegionalRegressionPredictInputs; expected_model_signature?: string },
): Promise<RegionalRegressionPredictResponse> {
  const { data } = await api.post<RegionalRegressionPredictResponse>(
    "/analysis/regional-regression/predict",
    body,
  );
  return data;
}
