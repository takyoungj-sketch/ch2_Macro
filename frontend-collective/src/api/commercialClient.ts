import axios from "axios";
import type {
  CommercialAssetType,
  CommercialAddressListResponse,
  CommercialClusterListResponse,
  CommercialFilterMeta,
  CommercialFloorIndexResponse,
  CommercialHistogramResponse,
  CommercialRegressionResponse,
  CommercialTransactionListResponse,
  CommercialYearlyStatsResponse,
  RegionOption,
  RegionStructure,
} from "../types";

const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();
const api = axios.create({
  baseURL: "/api/collective/commercial",
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

export async function fetchCommercialFilterMeta(): Promise<CommercialFilterMeta> {
  const { data } = await api.get<CommercialFilterMeta>("/meta/filters");
  return data;
}

export async function fetchCommercialAddr2(addr1: string): Promise<string[]> {
  const { data } = await api.get<string[]>("/regions/addr2", { params: { addr1 } });
  return data;
}

export async function fetchCommercialAddr3(
  addr1: string,
  addr2: string,
  assetType?: CommercialAssetType,
): Promise<RegionOption[]> {
  const { data } = await api.get<RegionOption[]>("/regions/addr3", {
    params: { addr1, addr2, asset_type: assetType },
  });
  return data;
}

export async function fetchCommercialRegionStructure(
  addr1: string,
  addr2: string,
  assetType?: CommercialAssetType,
): Promise<RegionStructure> {
  const { data } = await api.get<RegionStructure>("/regions/structure", {
    params: { addr1, addr2, asset_type: assetType },
  });
  return data;
}

export async function fetchCommercialLeafRegions(
  addr1: string,
  addr2: string,
  addr3List: string[],
  assetType?: CommercialAssetType,
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

export async function fetchCommercialClusters(params: {
  asset_type?: CommercialAssetType;
  addr1?: string;
  addr2?: string;
  addr3_list?: string[];
  addr4_list?: string[];
  contract_year_from?: number;
  contract_year_to?: number;
  sort?: string;
  page?: number;
  page_size?: number;
}): Promise<CommercialClusterListResponse> {
  const { data } = await api.get<CommercialClusterListResponse>("/clusters", {
    params,
    paramsSerializer: { indexes: null },
  });
  return data;
}

export async function fetchCommercialTransactions(
  clusterKey: string,
  params?: {
    addr1?: string;
    addr2?: string;
    addr3_list?: string[];
    addr4_list?: string[];
    contract_year_from?: number;
    contract_year_to?: number;
    page?: number;
    page_size?: number;
  },
): Promise<CommercialTransactionListResponse> {
  const { data } = await api.get<CommercialTransactionListResponse>(`/clusters/${clusterKey}/transactions`, {
    params,
    paramsSerializer: { indexes: null },
  });
  return data;
}

type ClusterScopeParams = {
  addr1?: string;
  addr2?: string;
  addr3_list?: string[];
  addr4_list?: string[];
  contract_year_from?: number;
  contract_year_to?: number;
};

export async function fetchCommercialYearlyStats(
  clusterKey: string,
  params?: ClusterScopeParams,
): Promise<CommercialYearlyStatsResponse> {
  const { data } = await api.get<CommercialYearlyStatsResponse>(`/clusters/${clusterKey}/stats/by-year`, {
    params,
    paramsSerializer: { indexes: null },
  });
  return data;
}

export async function fetchCommercialHistogram(
  clusterKey: string,
  params?: ClusterScopeParams & { bins?: number; contract_year?: number },
): Promise<CommercialHistogramResponse> {
  const { data } = await api.get<CommercialHistogramResponse>(`/clusters/${clusterKey}/histogram`, {
    params,
    paramsSerializer: { indexes: null },
  });
  return data;
}

export async function fetchCommercialAddresses(
  clusterKey: string,
  params?: ClusterScopeParams,
): Promise<CommercialAddressListResponse> {
  const { data } = await api.get<CommercialAddressListResponse>(`/clusters/${clusterKey}/addresses`, {
    params,
    paramsSerializer: { indexes: null },
  });
  return data;
}

export async function fetchCommercialFloorIndex(
  clusterKey: string,
  params?: ClusterScopeParams & { dimension?: "floor" | "area"; experiment?: boolean },
): Promise<CommercialFloorIndexResponse> {
  const { data } = await api.get<CommercialFloorIndexResponse>(`/clusters/${clusterKey}/floor-index`, {
    params: {
      ...params,
      experiment: params?.experiment ? true : undefined,
    },
    paramsSerializer: { indexes: null },
  });
  return data;
}

export async function runCommercialRegression(
  clusterKey: string,
  body: ClusterScopeParams & {
    exclude_outliers_iqr?: boolean;
    experiment?: boolean;
    variables?: {
      gross_area?: boolean;
      land_area?: boolean;
      building_age?: boolean;
      floor?: boolean;
      zone_type?: boolean;
      building_use?: boolean;
      road_width?: boolean;
      road_code?: boolean;
      addr4?: boolean;
      floor_mode?: "linear" | "dummy" | "grouped" | "relative";
    };
  },
): Promise<CommercialRegressionResponse> {
  const { data } = await api.post<CommercialRegressionResponse>(`/clusters/${clusterKey}/regression/run`, {
    variables: {
      gross_area: true,
      building_age: true,
      floor: true,
      zone_type: true,
      building_use: true,
      road_width: true,
      floor_mode: "relative",
      ...body.variables,
    },
    exclude_outliers_iqr: body.exclude_outliers_iqr ?? false,
    experiment: body.experiment ?? false,
    addr1: body.addr1,
    addr2: body.addr2,
    addr3_list: body.addr3_list,
    addr4_list: body.addr4_list,
    contract_year_from: body.contract_year_from,
    contract_year_to: body.contract_year_to,
  });
  return data;
}
