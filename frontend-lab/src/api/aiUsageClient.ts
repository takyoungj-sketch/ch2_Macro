import axios from "axios";
import { adminHeaders } from "./qaClient";

const api = axios.create({
  baseURL: "/api",
  timeout: 30_000,
});
// 관리자 API: QA 토큰을 요청마다 읽어 붙인다(패널에서 토큰을 바꿔도 반영).
api.interceptors.request.use((config) => {
  Object.entries(adminHeaders()).forEach(([key, value]) => config.headers.set(key, value));
  return config;
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
  /** 질문 단위 집계 (2026-11-09 §5.6) */
  questions?: {
    questions: number;
    answered_with_llm: number;
    avg_llm_calls: number | null;
    avg_krw: number | null;
    latency_p50_ms: number | null;
    latency_p90_ms: number | null;
    validation: Record<string, number>;
  };
  limit_warnings?: string[];
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
