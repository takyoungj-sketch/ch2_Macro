import axios from "axios";

const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();
const api = axios.create({
  baseURL: "/api",
  timeout: 120_000,
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

export type SizeLevel = "sigungu" | "eupmyeondong" | "beopjungri";
export type SizeMetric = "amount" | "count";

export type SizeCorr = {
  n: number;
  r: number | null;
  n_pop?: number;
  r_pop?: number | null;
  n_parents?: number;
};

export type SizePair = {
  a: string;
  b: string;
  amount: SizeCorr;
  count: SizeCorr;
  share_amount: { n: number; r: number | null };
  share_count: { n: number; r: number | null };
  within_amount?: SizeCorr;
  within_count?: SizeCorr;
};

export type SizePricePair = {
  a: string;
  b: string;
  price: { n: number; r: number | null };
  within_price: { n: number; r: number | null; n_parents?: number };
};

export type SizePopAxis = {
  type: string;
  amount: SizeCorr;
  count: SizeCorr;
};

export type SizeScatterPoint = {
  code: string;
  name: string;
  x: number;
  y: number;
  x_raw: number;
  y_raw: number;
  population: number | null;
};

export type SizeLabResponse = {
  lab: string;
  note: string;
  profile_version: string;
  window_years: number;
  region_level: SizeLevel;
  as_of_month: string;
  universe_n: number;
  n: number;
  dropped_dong: number;
  added_city?: number;
  types: string[];
  price_types?: string[];
  price_missing_types?: string[];
  price_note?: string;
  presence?: { type: string; n_pos: number; pct: number }[];
  core4_n?: number;
  pairs: SizePair[];
  price_pairs?: SizePricePair[];
  population_axis: SizePopAxis[];
  scatter: {
    a: string;
    b: string;
    metric: SizeMetric;
    log: boolean;
    points: SizeScatterPoint[];
    n_positive: number;
  } | null;
};

export async function fetchMarketSizeLab(params: {
  regionLevel: SizeLevel;
  scatterA?: string;
  scatterB?: string;
  scatterMetric?: SizeMetric;
}): Promise<SizeLabResponse> {
  const { data } = await api.get<SizeLabResponse>("/regional-profile/lab/market-size", {
    params: {
      region_level: params.regionLevel,
      scatter_a: params.scatterA,
      scatter_b: params.scatterB,
      scatter_metric: params.scatterMetric,
    },
  });
  return data;
}
