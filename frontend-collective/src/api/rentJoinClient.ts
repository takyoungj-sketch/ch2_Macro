import axios from "axios";

const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();
const api = axios.create({
  baseURL: "/api/rent",
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

export type RentJoinMetric = {
  n: number;
  median?: number | null;
};

export type RentSaleJoinResponse = {
  joined: boolean;
  reason: string;
  sale_building_key?: string;
  rent_building_key?: string | null;
  asset_type?: string;
  as_of_month?: string | null;
  window_years: number;
  period_start?: string | null;
  period_end?: string | null;
  building?: {
    display_name: string;
    jeonse: RentJoinMetric;
    mixed: { n: number; deposit: RentJoinMetric; monthly: RentJoinMetric };
    monthly: RentJoinMetric;
    jeonse_equiv: RentJoinMetric;
    monthly_equiv: RentJoinMetric;
  } | null;
  conversion?: {
    r_selected?: number | null;
    scope?: string;
    fallback?: boolean;
    gate_passed?: boolean;
  } | null;
  conversion_applied: boolean;
  conversion_fallback: boolean;
};

export async function fetchSaleRentJoin(params: {
  saleBuildingKey: string;
  assetType: string;
  windowYears: number;
}): Promise<RentSaleJoinResponse> {
  const { data } = await api.get<RentSaleJoinResponse>("/sale-join", {
    params: {
      sale_building_key: params.saleBuildingKey,
      asset_type: params.assetType,
      window_years: params.windowYears,
    },
  });
  return data;
}
