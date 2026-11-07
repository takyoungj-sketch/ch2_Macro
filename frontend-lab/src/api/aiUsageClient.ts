import axios from "axios";

const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();
const api = axios.create({
  baseURL: "/api",
  timeout: 30_000,
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

export type AiUsageEvent = {
  ts: string;
  requested_model?: string;
  served_model?: string | null;
  prompt_tokens?: number;
  completion_tokens?: number;
  usd?: number;
  krw?: number;
  route?: string;
  app?: string;
  panel?: string;
  scope_label?: string;
};

export type AiUsageSnapshot = {
  month: string;
  calls: number;
  call_limit: number;
  usd: number;
  krw: number;
  budget_krw: number;
  usd_krw: number;
  warn: boolean;
  stopped: boolean;
  warning?: string | null;
  requested_model?: string;
  recent: AiUsageEvent[];
};

export async function fetchAiUsage(month?: string): Promise<AiUsageSnapshot> {
  const { data } = await api.get<AiUsageSnapshot>("/admin/ai-usage", {
    params: month ? { month } : undefined,
  });
  return data;
}

export type AiAccountUsage = {
  enabled: boolean;
  balances: { user_id: number; feature: string; used: number; reserved: number; limit_units: number; period_end: string }[];
  costs: { stage: string; status: string; calls: number; estimated_usd: number | null }[];
  pending?: { id: string; user_id: number; feature: string; created_at: string }[];
};
export async function fetchAiAccountUsage(): Promise<AiAccountUsage> {
  return (await api.get<AiAccountUsage>("/admin/ai-usage/accounts")).data;
}
