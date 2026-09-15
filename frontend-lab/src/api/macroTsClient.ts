import axios from "axios";

const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();
const api = axios.create({
  baseURL: "/api",
  timeout: 120_000,
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

export type MacroPoint = { year?: number; month?: string; v: number };
export type MacroCorr = { n: number; r: number | null; lag: number };
export type MacroGrain = "calendar_year" | "calendar_month";

export type MacroRate = {
  id: string;
  label: string;
  role: string;
  unit: string;
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

export type MacroTsResponse = {
  lab: string;
  note: string;
  grain: MacroGrain | string;
  default_rate: string;
  years: number[];
  periods?: string[];
  lags?: number[];
  rates: Record<string, MacroRate>;
  m2: { values: MacroPoint[]; yoy_pct: MacroPoint[]; unit: string } | null;
  missing: string[];
  types: string[];
  series: Record<string, MacroTypeSeries>;
  pairs: MacroPairRow[];
  coverage_notes: string[];
  sources: Record<string, string | null>;
};

export async function fetchMacroTs(grain: MacroGrain = "calendar_year"): Promise<MacroTsResponse> {
  const { data } = await api.get<MacroTsResponse>("/regional-profile/lab/macro-ts", {
    params: { grain },
  });
  return data;
}
