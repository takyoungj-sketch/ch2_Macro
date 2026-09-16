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
