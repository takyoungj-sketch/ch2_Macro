// @ts-nocheck
import axios from "axios";
import { withVisibleInsightReport } from "./insightReportContext";

const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();
const api = axios.create({
  baseURL: "/api/ai",
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

export type AiApp = "land" | "built" | "collective" | "rent" | "profile" | "insight";
export type AiPurpose = "statistics" | "prediction" | "market_analysis" | "methodology";

export type EvidenceConfidence = "high" | "medium" | "low";

export interface EvidenceItem {
  type: string;
  label: string;
  ref?: string | null;
  value?: string | null;
  url?: string | null;
  confidence: EvidenceConfidence;
}

export interface AiScreenAction {
  id: string;
  kind: "navigate" | "open_ui" | "run_engine";
  label: string;
  href?: string | null;
  ui?: string | null;
  path_id?: string | null;
  confirm_message?: string | null;
}

export interface AiChatResponse {
  quota?: AiAllowance;
  session_id: string;
  route: string;
  answer: string;
  answer_context?: { app: AiApp; panel: string; purpose: AiPurpose; scope: AiContextPayload["scope"] };
  evidence: EvidenceItem[];
  bundle_id?: string | null;
  suggested_followups: string[];
  actions?: AiScreenAction[];
  disclaimer?: string | null;
  llm_used: boolean;
  trust_level?: "high" | "medium" | "low" | null;
  trust_sources?: string[];
  ai_interpretation?: string | null;
}

export interface AiAllowance {
  mode?: string;
  plan?: string;
  period_end?: string;
  items: { feature: string; label: string; used: number; reserved: number; remaining: number; limit: number; warn: boolean; unit: string }[];
}

export async function fetchAiAllowance(): Promise<AiAllowance> {
  return (await api.get<AiAllowance>("/allowance")).data;
}

const PENDING_REQUEST_KEY = "ch2_ai_pending_request";
export async function fetchPendingAiResult(): Promise<AiChatResponse | null> {
  let key: string | null;
  try { key = sessionStorage.getItem(PENDING_REQUEST_KEY); } catch { return null; }
  if (!key) return null;
  try {
    const { data } = await api.get(`/requests/${encodeURIComponent(key)}`);
    if (data.status === "completed" || data.status === "failed") sessionStorage.removeItem(PENDING_REQUEST_KEY);
    return data.status === "completed" ? data.result : null;
  } catch (error) {
    if (error?.response?.status === 404 || error?.response?.status === 401) sessionStorage.removeItem(PENDING_REQUEST_KEY);
    return null;
  }
}

export interface AiContextPayload {
  app: AiApp;
  panel: string;
  purpose: AiPurpose;
  scope: {
    region_label?: string;
    region_codes?: string[];
    asset_type?: string;
    filters?: Record<string, unknown>;
    /** 토지 매트릭스 문맥 공통 scope (2026-11-09 §5.1) */
    region_level?: string;
    region_code_count?: number;
    period?: Record<string, unknown>;
    as_of_month?: string;
    stats_reference_date?: string;
  };
  facts: Record<string, unknown>;
  explain?: unknown;
}

const SESSION_STORAGE_KEY = "ch2_ai_session_id";

export function readAiSessionId(): string | null {
  try {
    return sessionStorage.getItem(SESSION_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function writeAiSessionId(id: string) {
  try {
    sessionStorage.setItem(SESSION_STORAGE_KEY, id);
  } catch {
    /* ignore */
  }
}

export async function fetchSuggestedQuestions(
  panel: string,
  purpose: AiPurpose = "statistics",
  app: AiApp = "built",
): Promise<string[]> {
  const { data } = await api.get<{ questions: string[] }>("/suggested-questions", {
    params: { app, panel, purpose },
  });
  return data.questions ?? [];
}

export function isAiChatAborted(err: unknown): boolean {
  if (!err || typeof err !== "object") return false;
  const e = err as { code?: string; name?: string; message?: string };
  const msg = String(e.message || "").toLowerCase();
  return (
    e.code === "ERR_CANCELED" ||
    e.name === "CanceledError" ||
    e.name === "AbortError" ||
    msg === "canceled" ||
    msg === "cancelled"
  );
}

export async function sendAiChat(
  message: string,
  context: AiContextPayload,
  sessionId?: string | null,
  opts?: { signal?: AbortSignal },
): Promise<AiChatResponse> {
  const sid = sessionId ?? readAiSessionId() ?? undefined;
  const requestId = crypto.randomUUID();
  try { sessionStorage.setItem(PENDING_REQUEST_KEY, requestId); } catch { /* optional recovery */ }
  const { data } = await api.post<AiChatResponse>(
    "/chat",
    {
      session_id: sid,
      request_id: requestId,
      message,
      context: withVisibleInsightReport(context),
    },
    { signal: opts?.signal },
  );
  if (data?.session_id) writeAiSessionId(data.session_id);
  try { if (sessionStorage.getItem(PENDING_REQUEST_KEY) === requestId) sessionStorage.removeItem(PENDING_REQUEST_KEY); } catch { /* optional recovery */ }
  return data;
}

export async function recordAnalysisHistory(
  context: AiContextPayload,
  message?: string,
): Promise<{ session_id: string; recorded: boolean; slot_id?: string | null; history_len: number }> {
  const { data } = await api.post("/history", {
    session_id: readAiSessionId() ?? undefined,
    context,
    message,
  });
  if (data?.session_id) writeAiSessionId(data.session_id);
  return data;
}
