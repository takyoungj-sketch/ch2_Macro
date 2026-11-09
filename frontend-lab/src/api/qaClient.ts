import axios from "axios";

const TOKEN_KEY = "ch2-qa-audit-token";

export function readQaToken(): string {
  try {
    return (localStorage.getItem(TOKEN_KEY) || "").trim();
  } catch {
    return "";
  }
}

export function writeQaToken(token: string) {
  try {
    localStorage.setItem(TOKEN_KEY, token.trim());
  } catch {
    /* ignore */
  }
}

/**
 * `/api/admin/*`, `/api/lab/*` 공통 헤더. 서버는 관리자 세션 또는 `X-Qa-Audit-Token` 만 연다.
 * 토큰은 QA·대장DB 패널에서 저장한 값을 요청 시점에 읽는다. 랩은 nginx 기본인증 뒤에 있다.
 */
export function adminHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...(extra ?? {}) };
  const apiToken = (import.meta.env.VITE_API_TOKEN ?? "").trim();
  if (apiToken) headers["X-Api-Token"] = apiToken;
  const qaToken = readQaToken();
  if (qaToken) headers["X-Qa-Audit-Token"] = qaToken;
  return headers;
}

function qaApi() {
  return axios.create({
    baseURL: "/api/admin/qa",
    timeout: 180_000,
    headers: adminHeaders(),
  });
}

export type QaCheck = {
  id: string;
  label: string;
  grade: string;
  detail: string;
};

export type QaRun = {
  verdict?: string;
  verdict_ui?: string;
  domain?: string;
  region_name?: string;
  region_code?: string;
  region_level?: string;
  period_key?: string;
  asset_type?: string;
  asset_label?: string;
  trigger?: string;
  ai_report?: string;
  log_path?: string;
  id?: number;
  diffs?: {
    metrics?: Record<
      string,
      {
        l1?: number | null;
        l3?: number | null;
        mart?: number | null;
        delta_l1_mart?: number | null;
        grade?: string;
        reason?: string;
      }
    >;
    checks?: QaCheck[];
    cause_candidates?: string[];
  };
  l2?: { drop_chain?: Record<string, number | null>; n_needs_review?: number };
};

export async function runSpecified(body: {
  calendar_year: number;
  region_code?: string;
  region_name?: string;
  asset_type?: string;
  domain?: string;
  save_db?: boolean;
}): Promise<QaRun> {
  const { data } = await qaApi().post<QaRun>("/specified", body);
  return data;
}

export async function runRandom(body: {
  calendar_year?: number;
  asset_type?: string;
  domain?: string;
  n: number;
  save_db?: boolean;
}): Promise<{ runs: QaRun[]; count: number }> {
  const { data } = await qaApi().post<{ runs: QaRun[]; count: number }>("/random", body);
  return data;
}

export async function fetchQaRuns(limit = 15, domain?: string) {
  const { data } = await qaApi().get<{
    items: Array<{
      id: number;
      created_at: string;
      trigger: string;
      domain?: string;
      region_name: string | null;
      region_code: string;
      period_key: string;
      verdict: string;
    }>;
  }>("/runs", { params: { limit, domain } });
  return data;
}
