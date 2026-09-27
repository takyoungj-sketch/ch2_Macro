import axios from "axios";

const token = (import.meta.env.VITE_API_TOKEN ?? "").trim();
const api = axios.create({
  baseURL: "/api/admin/land-twin",
  timeout: 60_000,
  headers: token ? { "X-Api-Token": token } : undefined,
});

export type LandTwinRegion = { region_code: string; label: string };

export type LandTwinRegions = {
  as_of_month: string;
  window_years: number;
  period_start: string | null;
  period_end: string | null;
  regions: LandTwinRegion[];
};

export type LandTwinRow = {
  structure_rank: number;
  price_rank: number | null;
  rank_b: number | null;
  rank_c: number | null;
  rank_d: number | null;
  region_code: string;
  label: string;
  structure_similarity: number;
  zone_similarity: number | null;
  price_distance: number | null;
  cell_distance: number | null;
  shared_count: number;
  shared_jimok: string[];
  shared_cell_count: number;
  shared_cells: string[];
  cell_level_phrase: string | null;
  zone_count: number;
  level_gap: number | null;
  level_phrase: string | null;
  n_tx: number;
};

export type BasketShare = { cell: string; share: number; count: number };

export type BasketRow = {
  rank: number;
  region_code: string;
  label: string;
  structure_similarity: number;
  price_distance: number | null;
  price_cells: number;
  scale_ratio: number;
  scale_phrase: string | null;
};

export type LandTwinRun = {
  as_of_month: string;
  window_years: number;
  period_start: string | null;
  period_end: string | null;
  anchor: {
    region_code: string;
    label: string;
    n_tx: number;
    n_jimok: number;
    n_zone: number;
    basket_total: number;
    basket_shares: BasketShare[];
  };
  rows: LandTwinRow[];
  basket_note: string | null;
  basket_rows: BasketRow[];
};

export async function fetchLandTwinRegions(): Promise<LandTwinRegions> {
  const { data } = await api.get<LandTwinRegions>("/regions");
  return data;
}

export async function runLandTwin(regionCode: string): Promise<LandTwinRun> {
  const { data } = await api.post<LandTwinRun>("/run", { region_code: regionCode });
  return data;
}
