import axios from "axios";

const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();
const api = axios.create({
  baseURL: "/api",
  timeout: 180_000,
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

export type AssetType = "commercial" | "factory" | "detached";

export type BenchCase = {
  case_id: string;
  label: string;
  asset_type: AssetType;
  region_code: string;
  sample_group?: string;
  tx_n?: number;
  sido_prefix?: string | null;
  basin?: string | null;
};

export type BenchColumn = {
  id: string;
  label: string;
  skipped_reason?: string | null;
  n?: number | null;
  search_cv_mape?: number | null;
  confirm_cv_mape?: number | null;
  blocks?: string[];
  response_scale?: string | null;
  y_hat?: number | null;
  ci_lower?: number | null;
  ci_upper?: number | null;
  pi_lower?: number | null;
  pi_upper?: number | null;
  predict_skipped_reason?: string | null;
  predict_warnings?: string[];
};

export type BenchResult = {
  asset_type: string;
  admin_level: string;
  region_code: string;
  window_years?: number | null;
  rank1_region_code?: string | null;
  rank1_skipped_reason?: string | null;
  local_obs: { n: number; mean?: number | null; p50?: number | null };
  scenario: Record<string, unknown>;
  stage1_blocks?: string[];
  stage1_scale?: string;
  columns: BenchColumn[];
  twin_gates?: { region_code: string; rank?: number | null; accepted: boolean; reasons: string[] }[];
};

export type TwinNeighbor = {
  region_code: string;
  similarity_score?: number | null;
  detail_scores?: Record<string, unknown> | null;
};

function apiError(e: unknown): Error {
  const ax = e as { response?: { data?: { detail?: unknown } }; message?: string };
  const d = ax.response?.data?.detail;
  const msg =
    typeof d === "string"
      ? d
      : Array.isArray(d)
        ? d.map((x: { msg?: string }) => x.msg || JSON.stringify(x)).join("; ")
        : ax.message;
  return new Error(msg || "요청 실패");
}

export async function fetchBenchCases(): Promise<BenchCase[]> {
  try {
    const { data } = await api.get<{ items: BenchCase[] }>("/built/lab/recommend-twin-bench/cases");
    return data.items ?? [];
  } catch (e) {
    throw apiError(e);
  }
}

export type TwinFetch = {
  profile_version?: string | null;
  profile_as_of_month?: string | null;
  profile_window_years?: number | null;
  neighbors: TwinNeighbor[];
};

export async function fetchProfileTwins(
  regionCode: string,
  opts: { windowYears: number; twinProfile: "general" | "built_commercial" },
): Promise<TwinFetch> {
  try {
    const { data } = await api.get(`/regional-profile/twins/${regionCode}`, {
      params: {
        window_years: Math.min(5, Math.max(1, opts.windowYears)),
        top_k: 5,
        scope: "region",
        twin_profile: opts.twinProfile,
      },
    });
    const rows = data?.neighbors ?? [];
    const neighbors = rows
      .map((n: Record<string, unknown>) => ({
        region_code: String(n.twin_beopjungri_code || n.twin_eupmyeondong_code || "").trim(),
        similarity_score: typeof n.similarity_score === "number" ? n.similarity_score : null,
        detail_scores: (n.detail_scores as Record<string, unknown> | null) ?? null,
      }))
      .filter((n: TwinNeighbor) => n.region_code);
    return {
      profile_version: data?.profile_version ?? null,
      profile_as_of_month: data?.as_of_month ?? null,
      profile_window_years: typeof data?.window_years === "number" ? data.window_years : null,
      neighbors,
    };
  } catch (e) {
    throw apiError(e);
  }
}

export async function runRecommendTwinBench(body: {
  asset_type: AssetType;
  region_code: string;
  window_years: number;
  profile_twin_neighbors: TwinNeighbor[];
  profile_version?: string | null;
  profile_as_of_month?: string | null;
  profile_window_years?: number | null;
}): Promise<BenchResult> {
  try {
    const { data } = await api.post<BenchResult>("/built/lab/recommend-twin-bench", body);
    return data;
  } catch (e) {
    throw apiError(e);
  }
}
