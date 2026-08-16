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

function qaApi() {
  const token = readQaToken();
  return axios.create({
    baseURL: "/api/admin/qa",
    timeout: 180_000,
    headers: token ? { "X-Qa-Audit-Token": token } : undefined,
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
  save_db?: boolean;
}): Promise<QaRun> {
  const { data } = await qaApi().post<QaRun>("/specified", body);
  return data;
}

export async function runRandom(body: {
  calendar_year?: number;
  asset_type?: string;
  n: number;
  save_db?: boolean;
}): Promise<{ runs: QaRun[]; count: number }> {
  const { data } = await qaApi().post<{ runs: QaRun[]; count: number }>("/random", body);
  return data;
}

export async function fetchQaRuns(limit = 15) {
  const { data } = await qaApi().get<{
    items: Array<{
      id: number;
      created_at: string;
      trigger: string;
      region_name: string | null;
      region_code: string;
      period_key: string;
      verdict: string;
    }>;
  }>("/runs", { params: { limit } });
  return data;
}
