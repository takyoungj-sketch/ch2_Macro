import axios from "axios";

const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();
const api = axios.create({
  baseURL: "/api",
  timeout: 120_000,
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

export type YearPoint = { year: number; v: number };

export type AnnualSmoke = {
  year: number;
  re_eok: number | null;
  gdp_eok: number | null;
  m2_eok: number | null;
  stock_eok: number | null;
  vs_gdp_pct: number | null;
  vs_m2_pct: number | null;
  vs_stock_pct: number | null;
  unit_ok: boolean;
};

export type AnnualScaleResponse = {
  lab: string;
  note: string;
  grain: string;
  unit: string;
  ratio_unit: string;
  as_of: string;
  year_start: number;
  year_end: number;
  years: number[];
  types: string[];
  sources: Record<string, string | null | undefined>;
  coverage_notes: string[];
  missing: string[];
  levels_eok: {
    re_total: YearPoint[];
    gdp: YearPoint[];
    m2: YearPoint[];
    stock: YearPoint[];
  };
  ratios: {
    vs_gdp: YearPoint[];
    vs_m2: YearPoint[];
    vs_stock: YearPoint[];
  };
  mix: {
    types: string[];
    share: Record<string, YearPoint[]>;
    amount_eok: Record<string, YearPoint[]>;
  };
  type_vs_gdp: Record<string, YearPoint[]>;
  corr?: {
    n_level: number;
    n_yoy: number;
    level: Record<string, number | null>;
    yoy: Record<string, number | null>;
    read: string;
  };
  smoke: Record<string, AnnualSmoke>;
  limits: string[];
  resume?: {
    next_id: string;
    title: string;
    say: string;
    do_not: string;
    how: string;
  };
};

export async function fetchAnnualScale(): Promise<AnnualScaleResponse> {
  const { data } = await api.get<AnnualScaleResponse>("/regional-profile/lab/macro-annual-scale");
  return data;
}
