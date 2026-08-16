import axios from "axios";

const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();
const labApi = axios.create({
  baseURL: "/api",
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

export type TwinLabVersionKey = "v0" | "v1" | "v2" | "v3" | "v2x" | "r0" | "r1" | "t1" | "rt";

export type TwinLabTwin = {
  region_code?: string | null;
  label?: string | null;
  similarity?: number | null;
};

export type TwinLabVersionResult = {
  cv_mape?: number | null;
  delta_pp?: number | null;
  lift_rel?: number | null;
  hit?: boolean | null;
  n?: number | null;
  n_local?: number | null;
  n_pool?: number | null;
  n_twins?: number | null;
  pool_id?: string | null;
  blocks?: string[] | null;
  region_blocks_selected?: string[] | null;
  region_blocks_candidate?: string[] | null;
  region_blocks_in_pool?: string[] | null;
  region_tier?: string | null;
  response_scale?: string | null;
  twins?: TwinLabTwin[];
  twin_profile?: string | null;
  stage2_ran?: boolean;
  error?: string;
};

export type TwinLabRegionRow = {
  case_id: string;
  region_code?: string;
  region_codes?: string[];
  region_label: string;
  admin_level?: string;
  role?: string;
  sample_group?: string;
  winner?: string | null;
  versions: Partial<Record<TwinLabVersionKey | string, TwinLabVersionResult>>;
};

export type TwinLabKpi = {
  n_regions?: number | null;
  median_cv_mape?: number | null;
  mean_cv_mape?: number | null;
  median_lift_rel?: number | null;
  mean_lift_rel?: number | null;
  hit_rate?: number | null;
  worsened_rate?: number | null;
  hit_threshold_rel?: number | null;
};

export type TwinLabExperiment = {
  experiment_id: string;
  asset_type?: string;
  period_years?: number;
  contract_year_from?: number;
  contract_year_to?: number;
  region_scope?: string;
  anchor_basin?: string;
  versions?: string[];
  kpis?: Partial<Record<string, TwinLabKpi>>;
  /** all / dev / holdout 등 — V3 holdout 검증용 */
  kpis_by_sample_group?: Partial<Record<string, Partial<Record<string, TwinLabKpi>>>>;
  /** V2 케이스 기준 고정 pool(top1/top3) ablation */
  pool_ablation_v2?: Partial<Record<string, TwinLabKpi>>;
  v2_twin_profile?: string | null;
  v2x_twin_profile?: string | null;
  region_feature_tier?: string | null;
  region_adoption?: {
    rt_cases_ok?: number;
    rt_better_than_t1?: number;
    selected_counts?: Record<string, number>;
    selected_when_rt_beats_t1?: Record<string, number>;
  };
  regions?: TwinLabRegionRow[];
  source?: string;
  notes?: string;
  generated_at?: string;
  n_regions?: number;
};

export type TwinLabListItem = {
  experiment_id: string;
  asset_type?: string;
  period_years?: number;
  anchor_basin?: string;
  versions?: string[];
  n_regions?: number;
  generated_at?: string;
  source?: string;
};

export async function fetchTwinLabExperiments(): Promise<{ items: TwinLabListItem[] }> {
  const { data } = await labApi.get<{ items: TwinLabListItem[] }>("/built/lab/twin-experiments");
  return data;
}

export async function fetchTwinLabExperiment(experimentId: string): Promise<TwinLabExperiment> {
  const { data } = await labApi.get<TwinLabExperiment>(
    `/built/lab/twin-experiments/${encodeURIComponent(experimentId)}`,
  );
  return data;
}

/** URL ?lab=twin|1 또는 VITE_TWIN_LAB=1 */
export function isTwinLabRequested(): boolean {
  if (typeof window === "undefined") return false;
  const params = new URLSearchParams(window.location.search);
  const q = (params.get("lab") || "").toLowerCase();
  if (q === "twin" || q === "1" || q === "true") return true;
  const env = (import.meta.env.VITE_TWIN_LAB as string | undefined)?.trim().toLowerCase();
  return env === "1" || env === "true" || env === "yes";
}
