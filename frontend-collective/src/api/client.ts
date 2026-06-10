/** 실험 단계: 분석 게이트 우회 + 모든 탭·옵션 항상 사용 (운영 전 false) */
export const COLLECTIVE_EXPERIMENT_MODE =
  import.meta.env.VITE_COLLECTIVE_EXPERIMENT === "true" || import.meta.env.DEV;

import axios from "axios";
import type {
  AssetType,
  BuildingListResponse,
  BuildingStatsRow,
  CollectiveFilterMeta,
  CollectiveRegressionResponse,
  CollectiveTransactionRow,
  FloorIndexResponse,
  HistogramResponse,
  RegionOption,
  RegionStructure,
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

export async function fetchAddr2(addr1: string, assetType?: AssetType): Promise<string[]> {
  const { data } = await api.get<string[]>("/regions/addr2", {
    params: { addr1, asset_type: assetType },
  });
  return data;
}

export async function fetchRegionStructure(
  addr1: string,
  addr2: string,
  assetType?: AssetType,
): Promise<RegionStructure> {
  const { data } = await api.get<RegionStructure>("/regions/structure", {
    params: { addr1, addr2, asset_type: assetType },
  });
  return data;
}

export async function fetchAddr3WithCounts(
  addr1: string,
  addr2: string,
  assetType?: AssetType,
): Promise<RegionOption[]> {
  const { data } = await api.get<RegionOption[]>("/regions/addr3", {
    params: { addr1, addr2, asset_type: assetType },
  });
  return data;
}

export async function fetchLeafRegions(
  addr1: string,
  addr2: string,
  addr3List: string[],
  assetType?: AssetType,
): Promise<RegionOption[]> {
  const { data } = await api.get<RegionOption[]>("/regions/leaf", {
    params: {
      addr1,
      addr2,
      asset_type: assetType,
      addr3_list: addr3List.length ? addr3List : undefined,
    },
    paramsSerializer: { indexes: null },
  });
  return data;
}

export async function fetchBuildings(params: {
  asset_type?: AssetType;
  addr1?: string;
  addr2?: string;
  addr3_list?: string[];
  addr4_list?: string[];
  contract_year_from?: number;
  contract_year_to?: number;
  sort?: string;
  page?: number;
  page_size?: number;
}): Promise<BuildingListResponse> {
  const { data } = await api.get<BuildingListResponse>("/buildings", {
    params,
    paramsSerializer: { indexes: null },
  });
  return data;
}

export async function fetchBuildingTransactions(
  buildingKey: string,
  params?: { contract_year_from?: number; contract_year_to?: number; page?: number; page_size?: number },
): Promise<{ total: number; items: CollectiveTransactionRow[] }> {
  const { data } = await api.get(`/buildings/${buildingKey}/transactions`, { params });
  return data;
}

export async function fetchBuildingHistogram(
  buildingKey: string,
  params?: { contract_year?: number; bins?: number },
): Promise<HistogramResponse> {
  const { data } = await api.get<HistogramResponse>(`/buildings/${buildingKey}/histogram`, { params });
  return data;
}

export async function fetchBuildingYearlyStats(
  buildingKey: string,
): Promise<{ points: YearlyStatPoint[] }> {
  const { data } = await api.get(`/buildings/${buildingKey}/stats/by-year`);
  return data;
}

export async function fetchBuildingFloorIndex(
  buildingKey: string,
  params?: {
    dimension?: "floor" | "dong" | "area" | "rights";
    contract_year_from?: number;
    contract_year_to?: number;
    experiment?: boolean;
  },
): Promise<FloorIndexResponse> {
  const { data } = await api.get<FloorIndexResponse>(`/buildings/${buildingKey}/floor-index`, {
    params: {
      ...params,
      experiment: params?.experiment ? true : undefined,
    },
  });
  return data;
}

export async function runBuildingRegression(
  buildingKey: string,
  body: {
    asset_type: AssetType;
    contract_year_from?: number;
    contract_year_to?: number;
    exclude_outliers_iqr?: boolean;
    experiment?: boolean;
    variables?: {
      exclusive_area?: boolean;
      building_age?: boolean;
      floor?: boolean;
      dong?: boolean;
      housing_subtype?: boolean;
      floor_mode?: "linear" | "dummy" | "grouped" | "relative";
    };
  },
): Promise<CollectiveRegressionResponse> {
  const { data } = await api.post<CollectiveRegressionResponse>(
    `/buildings/${buildingKey}/regression/run`,
    {
      variables: {
        exclusive_area: true,
        building_age: true,
        floor: true,
        dong: true,
        floor_mode: "relative",
        ...body.variables,
      },
      exclude_outliers_iqr: body.exclude_outliers_iqr ?? false,
      experiment: body.experiment ?? false,
      ...body,
    },
  );
  return data;
}

export type { BuildingStatsRow };
