// @ts-nocheck
import axios from "axios";

const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();
const api = axios.create({
  baseURL: "/api/ai",
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

export type AiApp = "land" | "built" | "collective" | "rent" | "profile";
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
  session_id: string;
  route: string;
  answer: string;
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

export interface AiContextPayload {
  app: AiApp;
  panel: string;
  purpose: AiPurpose;
  scope: {
    region_label?: string;
    asset_type?: string;
    filters?: Record<string, unknown>;
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

export async function sendAiChat(
  message: string,
  context: AiContextPayload,
  sessionId?: string | null,
): Promise<AiChatResponse> {
  const sid = sessionId ?? readAiSessionId() ?? undefined;
  const { data } = await api.post<AiChatResponse>("/chat", {
    session_id: sid,
    message,
    context,
  });
  if (data?.session_id) writeAiSessionId(data.session_id);
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
