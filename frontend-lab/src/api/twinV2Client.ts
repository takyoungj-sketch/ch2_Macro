import axios from "axios";

const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();
const api = axios.create({
  baseURL: "/api",
  timeout: 120_000,
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

export type TwinV2Level = "sigungu" | "eupmyeondong" | "beopjungri";
export type TwinV2Role = "compare" | "pool";

export type TwinV2Neighbor = {
  rank: number;
  region_code: string;
  region_name: string;
  sigungu_name: string;
  sido_name: string;
  twin_score: number;
  confidence: number;
  structure_score: number | null;
  market_score: number | null;
  used_blocks: string[];
  dropped_blocks: string[];
  detail?: Record<string, { score?: number; used?: boolean; note?: string }>;
  v1_similarity?: number | null;
};

export type TwinV2Response = {
  engine: string;
  weight_version: string;
  role: TwinV2Role;
  region_level: TwinV2Level;
  profile_version: string;
  window_years: number;
  as_of_month?: string | null;
  anchor: {
    region_code: string;
    region_name?: string;
    sigungu_name?: string;
    sido_name?: string;
    population?: number | null;
  };
  weights: { structure: number; market: number };
  universe: {
    kind: string;
    size: number;
    after_population_gate: number;
    gated_out_population?: number;
    n_hop?: number | null;
    graph_used?: boolean;
    fallback?: string | null;
    scope_label?: string;
  };
  neighbors: TwinV2Neighbor[];
};

export type RegionHit = {
  beopjungri_code: string;
  beopjungri_name: string;
  eupmyeondong_code: string;
  eupmyeondong_name: string;
  sigungu_code: string;
  sigungu_name: string;
  sido_code: string;
  sido_name: string;
};

export async function searchRegions(query: string): Promise<RegionHit[]> {
  const q = query.trim();
  if (q.length < 2) return [];
  const { data } = await api.get<RegionHit[]>("/free/v2/regions", {
    params: { search: q, limit: 40 },
  });
  return data;
}

export async function fetchTwinsV2(params: {
  regionLevel: TwinV2Level;
  regionCode: string;
  role: TwinV2Role;
  topK?: number;
}): Promise<TwinV2Response> {
  const { data } = await api.get<TwinV2Response>("/regional-profile/twins-v2", {
    params: {
      region_level: params.regionLevel,
      region_code: params.regionCode,
      role: params.role,
      top_k: params.topK ?? 8,
    },
  });
  return data;
}
