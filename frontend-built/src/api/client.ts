import axios from "axios";
import type {
  Addr3Option,
  BuiltFilterMeta,
  BuiltTransactionListResponse,
  RegionOption,
  RegionStructure,
  RegressionRunRequest,
  RegressionRunResponse,
  RegressionPredictRequest,
  RegressionPredictResponse,
  ScopeSampleFilterResponse,
} from "../types";

const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();
const api = axios.create({
  baseURL: "/api/built",
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

export interface TransactionQueryParams {
  asset_type?: string;
  addr1?: string;
  addr2?: string;
  addr3_list?: string[];
  addr4_list?: string[];
  ri_pick?: string[];
  zone_types?: string[];
  building_uses?: string[];
  gross_area_min?: number;
  gross_area_max?: number;
  land_area_min?: number;
  land_area_max?: number;
  building_age_min?: number;
  building_age_max?: number;
  road_code_min?: number;
  road_code_max?: number;
  contract_year_from?: number;
  contract_year_to?: number;
  page?: number;
  page_size?: number;
}

function toSearchParams(params: TransactionQueryParams): string {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value == null || value === "") return;
    if ((key === "addr3_list" || key === "addr4_list" || key === "ri_pick" || key === "zone_types" || key === "building_uses") && Array.isArray(value)) {
      value.forEach((v) => sp.append(key, v));
      return;
    }
    sp.append(key, String(value));
  });
  return sp.toString();
}

export async function fetchFilterMeta(): Promise<BuiltFilterMeta> {
  const { data } = await api.get<BuiltFilterMeta>("/meta/filters");
  return data;
}

export async function fetchRegionStructure(
  addr1: string,
  addr2: string,
  assetType?: string,
): Promise<RegionStructure> {
  const { data } = await api.get<RegionStructure>("/regions/structure", {
    params: { addr1, addr2, asset_type: assetType },
  });
  return data;
}

export async function fetchAddr2(addr1: string, assetType?: string): Promise<string[]> {
  const { data } = await api.get<string[]>("/regions/addr2", {
    params: { addr1, asset_type: assetType },
  });
  return data;
}

export async function fetchAddr3WithCounts(
  addr1: string,
  addr2: string,
  assetType?: string,
): Promise<Addr3Option[]> {
  const { data } = await api.get<Addr3Option[]>("/regions/addr3", {
    params: { addr1, addr2, asset_type: assetType, with_counts: true },
  });
  return data;
}

export async function fetchLeafRegions(
  addr1: string,
  addr2: string,
  guList: string[],
  assetType?: string,
): Promise<RegionOption[]> {
  const sp = new URLSearchParams({ addr1, addr2 });
  if (assetType) sp.append("asset_type", assetType);
  guList.forEach((g) => sp.append("addr3_list", g));
  const { data } = await api.get<RegionOption[]>(`/regions/leaf?${sp.toString()}`);
  return data;
}

export async function fetchRiRegions(
  addr1: string,
  addr2: string,
  opts: {
    leafLevel: string;
    addr3List?: string[];
    addr4List?: string[];
    assetType?: string;
  },
): Promise<RegionOption[]> {
  const sp = new URLSearchParams({ addr1, addr2, leaf_level: opts.leafLevel });
  if (opts.assetType) sp.append("asset_type", opts.assetType);
  (opts.addr3List ?? []).forEach((v) => sp.append("addr3_list", v));
  (opts.addr4List ?? []).forEach((v) => sp.append("addr4_list", v));
  const { data } = await api.get<RegionOption[]>(`/regions/ri?${sp.toString()}`);
  return data;
}

export async function fetchScopeSampleFilters(params: {
  asset_type?: string;
  addr1?: string;
  addr2?: string;
  addr3_list?: string[];
  addr4_list?: string[];
  ri_pick?: string[];
  contract_year_from?: number;
  contract_year_to?: number;
}): Promise<ScopeSampleFilterResponse> {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value == null || value === "") return;
    if ((key === "addr3_list" || key === "addr4_list" || key === "ri_pick") && Array.isArray(value)) {
      value.forEach((v) => sp.append(key, v));
      return;
    }
    sp.append(key, String(value));
  });
  const { data } = await api.get<ScopeSampleFilterResponse>(`/filters/scope?${sp.toString()}`);
  return data;
}

export async function fetchTransactions(params: TransactionQueryParams) {
  const qs = toSearchParams(params);
  const { data } = await api.get<BuiltTransactionListResponse>(`/transactions?${qs}`);
  return data;
}

export async function runRegression(body: RegressionRunRequest) {
  const { data } = await api.post<RegressionRunResponse>("/regression/run", body);
  return data;
}

export async function predictRegression(body: RegressionPredictRequest) {
  const { data } = await api.post<RegressionPredictResponse>("/regression/predict", body);
  return data;
}
