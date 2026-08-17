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
