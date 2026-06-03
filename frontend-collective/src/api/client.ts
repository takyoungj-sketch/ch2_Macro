import axios from "axios";
import type {
  AssetType,
  BuildingListResponse,
  BuildingStatsRow,
  CollectiveFilterMeta,
  CollectiveRegressionResponse,
  CollectiveTransactionRow,
  HistogramBin,
  YearlyStatPoint,
} from "../types";

const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();
const api = axios.create({
  baseURL: "/api/collective",
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

export async function fetchFilterMeta(): Promise<CollectiveFilterMeta> {
  const { data } = await api.get<CollectiveFilterMeta>("/meta/filters");
  return data;
}

export async function fetchAddr2(addr1: string): Promise<string[]> {
  const { data } = await api.get<string[]>("/regions/addr2", { params: { addr1 } });
  return data;
}

export async function fetchAddr3(
  addr1: string,
  addr2: string,
  assetType?: AssetType,
): Promise<{ name: string; count: number }[]> {
  const { data } = await api.get("/regions/addr3", {
    params: { addr1, addr2, asset_type: assetType },
  });
  return data;
}

export async function fetchBuildings(params: {
  asset_type?: AssetType;
  addr1?: string;
  addr2?: string;
  addr3?: string;
  contract_year_from?: number;
  contract_year_to?: number;
  sort?: string;
  page?: number;
  page_size?: number;
}): Promise<BuildingListResponse> {
  const { data } = await api.get<BuildingListResponse>("/buildings", { params });
  return data;
}

export async function fetchBuildingTransactions(
  buildingKey: string,
  params?: { contract_year_from?: number; contract_year_to?: number; page?: number },
): Promise<{ total: number; items: CollectiveTransactionRow[] }> {
  const { data } = await api.get(`/buildings/${buildingKey}/transactions`, { params });
  return data;
}

export async function fetchBuildingYearlyStats(
  buildingKey: string,
): Promise<{ points: YearlyStatPoint[] }> {
  const { data } = await api.get(`/buildings/${buildingKey}/stats/by-year`);
  return data;
}

export async function fetchBuildingHistogram(buildingKey: string): Promise<{ bins: HistogramBin[] }> {
  const { data } = await api.get(`/buildings/${buildingKey}/histogram`);
  return data;
}

export async function runBuildingRegression(
  buildingKey: string,
  body: {
    asset_type: AssetType;
    contract_year_from?: number;
    contract_year_to?: number;
    exclude_outliers_iqr?: boolean;
  },
): Promise<CollectiveRegressionResponse> {
  const { data } = await api.post<CollectiveRegressionResponse>(
    `/buildings/${buildingKey}/regression/run`,
    {
      variables: { exclusive_area: true, building_age: true, floor: true, dong: true },
      exclude_outliers_iqr: body.exclude_outliers_iqr ?? false,
      ...body,
    },
  );
  return data;
}

export type { BuildingStatsRow };
