import axios from "axios";

const token = (import.meta.env.VITE_API_TOKEN ?? "").trim();
const api = axios.create({
  baseURL: "/api/collective/analysis/regional-regression",
  timeout: 180_000,
  headers: token ? { "X-Api-Token": token } : undefined,
});

export type CoefRow = {
  variable: string;
  anchor: number;
  twin: number;
  same_sign: boolean;
  gap: number;
};

export type TwinRow = {
  region_id: string;
  label: string;
  distance: number;
  n_stock: number;
  n: number;
  gate: { pass: boolean; reason: string; cosine: number | null; sign_match: number; rows?: CoefRow[] };
};

export type PilotPlace = { addr1: string; addr2: string; addr4: string; label: string; n: number };

export type CvStep = {
  k: number;
  labels: string[];
  pool: number | null;
  dummy: number | null;
  pool_gain: number | null;
  dummy_gain: number | null;
  stop: boolean;
};

export type AptTwinResult = {
  as_of_label: string | null;
  region_name: string | null;
  anchor: { label: string; n: number; in_pilot_band: boolean; coefficients: Record<string, number> | null };
  twins: TwinRow[];
  pilot: PilotPlace[];
  steps: { role: string; folds: number; local: number | null; steps: CvStep[] } | null;
};

export async function runAptTwin(addr1: string, addr2: string, addr4: string): Promise<AptTwinResult> {
  const { data } = await api.post<AptTwinResult>("/apt-twin", { addr1, addr2, addr4 });
  return data;
}
