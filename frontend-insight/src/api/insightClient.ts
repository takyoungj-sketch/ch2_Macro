import axios from "axios";

const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();
const api = axios.create({
  baseURL: "/api",
  timeout: 180_000,
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

export type MacroPoint = { year?: number; month?: string; v: number };
export type MacroCorr = { n: number; r: number | null; lag: number };

export type MacroRate = {
  id: string;
  label: string;
  role?: string;
  unit?: string;
  values: MacroPoint[];
  d_pp: MacroPoint[];
};

export type MacroTypeSeries = {
  count: MacroPoint[];
  amount: MacroPoint[];
  yoy_count: MacroPoint[];
  yoy_amount: MacroPoint[];
};

export type MacroPairRow = {
  type: string;
  [key: string]: string | MacroCorr;
};

export type Insight01Response = {
  id: string;
  status: string;
  grain: string;
  as_of: string | null;
  period_start: string | null;
  period_end: string | null;
  default_rate: string;
  lags: number[];
  types: string[];
  rates: Record<string, MacroRate>;
  m2: { values: MacroPoint[]; yoy_pct: MacroPoint[]; unit?: string; label?: string } | null;
  series: Record<string, MacroTypeSeries>;
  pairs: MacroPairRow[];
  coverage_notes: string[];
  missing: string[];
  note?: string;
};

export async function fetchInsight01(): Promise<Insight01Response> {
  const { data } = await api.get<Insight01Response>("/insight/01");
  return data;
}

export function insight01AiFacts(data: Insight01Response) {
  return {
    insight_id: data.id,
    status: data.status,
    grain: data.grain,
    as_of: data.as_of,
    period_start: data.period_start,
    period_end: data.period_end,
    default_rate: data.default_rate,
    lags: data.lags,
    types: data.types,
    pairs: data.pairs,
    coverage_notes: data.coverage_notes,
    missing: data.missing,
    note: data.note,
  };
}

export type SizeMetric = "amount" | "count";
export type ScatterMetric = SizeMetric | "price";

export type SizeCorr = {
  n: number;
  r: number | null;
  n_pop?: number;
  r_pop?: number | null;
};

export type Insight02Pair = {
  a: string;
  b: string;
  amount: SizeCorr;
  count: SizeCorr;
};

export type Insight02PricePair = {
  a: string;
  b: string;
  n: number;
  r: number | null;
};

export type Insight02Presence = { type: string; n_pos: number; pct: number };

export type Insight02Response = {
  id: string;
  status: string;
  grain: string;
  window_years: number;
  as_of: string | null;
  n: number;
  universe_n: number;
  types: string[];
  price_types: string[];
  price_missing_types: string[];
  presence: Insight02Presence[];
  pairs: Insight02Pair[];
  price_pairs: Insight02PricePair[];
  note?: string;
};

export type Insight02ScatterPoint = {
  code: string;
  name: string;
  x: number;
  y: number;
  x_raw: number;
  y_raw: number;
  population: number | null;
};

export type Insight02ScatterResponse = {
  a: string;
  b: string;
  metric: ScatterMetric;
  log: boolean;
  n_positive: number;
  points: Insight02ScatterPoint[];
};

export async function fetchInsight02(): Promise<Insight02Response> {
  const { data } = await api.get<Insight02Response>("/insight/02");
  return data;
}

export async function fetchInsight02Scatter(
  a: string,
  b: string,
  metric: ScatterMetric,
): Promise<Insight02ScatterResponse> {
  const { data } = await api.get<Insight02ScatterResponse>("/insight/02/scatter", {
    params: { a, b, metric },
  });
  return data;
}

export function insight02AiFacts(data: Insight02Response) {
  return {
    insight_id: data.id,
    status: data.status,
    grain: data.grain,
    window_years: data.window_years,
    as_of: data.as_of,
    n: data.n,
    types: data.types,
    pairs: data.pairs,
    price_pairs: data.price_pairs,
    note: data.note,
  };
}

