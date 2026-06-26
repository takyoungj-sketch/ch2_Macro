import axios from "axios";

const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();
const api = axios.create({
  baseURL: "/api/ai",
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

export type AiApp = "land" | "built" | "collective";
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

export interface AiChatResponse {
  session_id: string;
  route: string;
  answer: string;
  evidence: EvidenceItem[];
  bundle_id?: string | null;
  suggested_followups: string[];
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
  const { data } = await api.post<AiChatResponse>("/chat", {
    session_id: sessionId ?? undefined,
    message,
    context,
  });
  return data;
}
