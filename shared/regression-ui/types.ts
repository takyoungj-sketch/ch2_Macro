export interface RegressionAnalysisContext {
  version: string;
  observation_unit: "transaction" | "complex";
  target: string;
  target_unit: string;
  response_scale: string;
  fit_n: number;
  coefficient_n: number;
  design_rank?: number | null;
  source_n?: number | null;
  model_signature: string;
  data_signature: string;
  fit_sample_signature?: string | null;
  feature_names: string[];
  variables: Array<{ name: string; state: "included" | "not_in_model" | "constant" | "no_data" | "missing_after_filter" | "not_identifiable"; columns: string[] }>;
  reference_categories?: Record<string, string>;
  sample_steps?: Array<{ label: string; n: number; excluded: number }>;
  sample_groups?: RegressionSampleGroup[];
  fit_years?: number[];
  assessed_years?: number[];
  provision?: { tier: "standard" | "caution" | "blocked"; identification_limited: boolean; residual_df: number; reasons: string[] } | null;
  metrics: Array<{
    validation?: RegressionValidationContext | null;
    key: string;
    role: "training" | "selection_validation" | "independent_confirmation";
    scale: string;
    value?: number | null;
    n?: number | null;
    method?: string | null;
    status: "available" | "unavailable";
    reason?: string | null;
    evaluation_signature?: string | null;
  }>;
}

export interface RegressionValidationContext {
  status: "available" | "partial" | "unavailable" | "not_run";
  method?: string;
  observation_unit?: "transaction" | "complex";
  requested_folds: number; attempted_folds: number; completed_folds: number;
  eligible_n: number; evaluated_n: number; excluded_n: number;
  reason_code?: string | null; reason?: string | null;
  failures: Array<{ fold: number; year?: number; code: string; reason: string }>;
}

export interface RegressionSampleGroup {
  key: string; label: string; address?: string; source_n: number; fit_n: number;
  fe_state: "reference" | "estimated" | "not_in_model" | "no_fit";
  confirmed_attributes?: Record<string, number>;
  structural_excluded_n?: number; linked_n?: number; unlinked_n?: number;
}

export interface RegressionComparisonContext {
  basis: "common_complete_case";
  observation_unit: "transaction" | "complex";
  sample_n: number;
  fit_n: number;
  evaluation_n?: number | null;
  method: string;
  role: "training" | "selection_validation";
  sample_signature?: string | null;
  evaluation_signature?: string | null;
}
