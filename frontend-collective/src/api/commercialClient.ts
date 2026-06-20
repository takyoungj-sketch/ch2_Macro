import axios from "axios";
import { filenameFromContentDisposition, saveBlobAsFile } from "../utils/downloadBlob";
import type {
  CommercialAssetSelectorType,
  CommercialAssetType,
  CommercialAddressListResponse,
  CommercialClusterListResponse,
  CommercialCohortFloorIndexResponse,
  CommercialCohortHistogramResponse,
  CommercialCohortRegressionResponse,
  CommercialCohortTransactionsResponse,
  CommercialRegressionPredictResponse,
  CommercialFilterMeta,
  CommercialFloorIndexResponse,
  CommercialHistogramResponse,
  CommercialPeerClusterListResponse,
  CommercialRegressionResponse,
  CommercialRollingStatsResponse,
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

function apiCommercialAssetParam(assetType?: CommercialAssetSelectorType): string | undefined {
  if (!assetType || assetType === "all") return undefined;
  return assetType;
}

export async function fetchCommercialFilterMeta(assetType?: CommercialAssetSelectorType): Promise<CommercialFilterMeta> {
  const { data } = await api.get<CommercialFilterMeta>("/meta/filters", {
    params: apiCommercialAssetParam(assetType) ? { asset_type: apiCommercialAssetParam(assetType) } : undefined,
  });
  return data;
}

export async function fetchCommercialAddr2(addr1: string, assetType?: CommercialAssetSelectorType): Promise<string[]> {
  const { data } = await api.get<string[]>("/regions/addr2", {
    params: { addr1, asset_type: apiCommercialAssetParam(assetType) },
  });
  return data;
}

export async function fetchCommercialAddr3(
  addr1: string,
  addr2: string,
  assetType?: CommercialAssetSelectorType,
): Promise<RegionOption[]> {
  const { data } = await api.get<RegionOption[]>("/regions/addr3", {
    params: { addr1, addr2, asset_type: apiCommercialAssetParam(assetType) },
  });
  return data;
}

export async function fetchCommercialRegionStructure(
  addr1: string,
  addr2: string,
  assetType?: CommercialAssetSelectorType,
): Promise<RegionStructure> {
  const { data } = await api.get<RegionStructure>("/regions/structure", {
    params: { addr1, addr2, asset_type: apiCommercialAssetParam(assetType) },
  });
  return data;
}

export async function fetchCommercialLeafRegions(
  addr1: string,
  addr2: string,
  addr3List: string[],
  assetType?: CommercialAssetSelectorType,
): Promise<RegionOption[]> {
  const { data } = await api.get<RegionOption[]>("/regions/leaf", {
    params: {
      addr1,
      addr2,
      asset_type: apiCommercialAssetParam(assetType),
      addr3_list: addr3List.length ? addr3List : undefined,
    },
    paramsSerializer: { indexes: null },
  });
  return data;
}

export async function fetchCommercialClusters(params: {
  asset_type?: CommercialAssetSelectorType;
  addr1?: string;
  addr2?: string;
  addr3_list?: string[];
  addr4_list?: string[];
  contract_year_from?: number;
  contract_year_to?: number;
  window_years?: number;
  sort?: string;
  page?: number;
  page_size?: number;
}): Promise<CommercialClusterListResponse> {
  const { data } = await api.get<CommercialClusterListResponse>("/clusters", {
    params: {
      ...params,
      asset_type: params.asset_type === "all" ? "all" : params.asset_type,
    },
    paramsSerializer: { indexes: null },
  });
  return data;
}

/** API page_size 상한(500)을 넘는 목록을 모두 조회 */
export async function fetchAllCommercialClusters(
  params: Omit<Parameters<typeof fetchCommercialClusters>[0], "page" | "page_size">,
): Promise<CommercialClusterListResponse> {
  const pageSize = 500;
  let page = 1;
  let meta: CommercialClusterListResponse | null = null;
  const items: CommercialClusterListResponse["items"] = [];

  while (true) {
    const batch = await fetchCommercialClusters({ ...params, page, page_size: pageSize });
    if (!meta) meta = batch;
    items.push(...batch.items);
    if (items.length >= batch.total || batch.items.length < pageSize) {
      return { ...(meta ?? batch), items, total: batch.total };
    }
    page += 1;
  }
}

export async function fetchCommercialTransactions(
  clusterKey: string,
  params?: ClusterScopeParams & { page?: number; page_size?: number },
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
  contract_date_from?: string;
  contract_date_to?: string;
  contract_year_from?: number;
  contract_year_to?: number;
};

export async function downloadCommercialTransactionsCsv(
  clusterKey: string,
  params?: ClusterScopeParams,
): Promise<void> {
  const response = await api.get<Blob>(`/clusters/${clusterKey}/transactions/export`, {
    params,
    paramsSerializer: { indexes: null },
    responseType: "blob",
  });
  const filename = filenameFromContentDisposition(
    response.headers["content-disposition"],
    "commercial_transactions.csv",
  );
  saveBlobAsFile(response.data, filename);
}

export async function fetchCommercialRollingStats(
  clusterKey: string,
  params?: { window_years?: number },
): Promise<CommercialRollingStatsResponse> {
  const { data } = await api.get<CommercialRollingStatsResponse>(`/clusters/${clusterKey}/stats/rolling`, {
    params,
  });
  return data;
}

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
    model_type?: "log" | "linear";
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
    model_type: body.model_type,
    addr1: body.addr1,
    addr2: body.addr2,
    addr3_list: body.addr3_list,
    addr4_list: body.addr4_list,
    contract_date_from: body.contract_date_from,
    contract_date_to: body.contract_date_to,
    contract_year_from: body.contract_year_from,
    contract_year_to: body.contract_year_to,
  });
  return data;
}

export async function predictCommercialRegression(
  clusterKey: string,
  body: Parameters<typeof runCommercialRegression>[1] & {
    inputs: import("../types").CommercialRegressionPredictInputs;
  },
): Promise<CommercialRegressionPredictResponse> {
  const { data } = await api.post<CommercialRegressionPredictResponse>(
    `/clusters/${clusterKey}/regression/predict`,
    {
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
      model_type: body.model_type,
      addr1: body.addr1,
      addr2: body.addr2,
      addr3_list: body.addr3_list,
      addr4_list: body.addr4_list,
      contract_date_from: body.contract_date_from,
      contract_date_to: body.contract_date_to,
      contract_year_from: body.contract_year_from,
      contract_year_to: body.contract_year_to,
      inputs: body.inputs,
    },
  );
  return data;
}

export async function predictCommercialCohortRegression(
  body: {
    cluster_keys: string[];
    asset_type?: CommercialAssetType;
    inputs: import("../types").CommercialRegressionPredictInputs;
    exclude_outliers_iqr?: boolean;
    experiment?: boolean;
    model_type?: "log" | "linear";
    variables?: Parameters<typeof runCommercialRegression>[1]["variables"];
    contract_date_from?: string;
    contract_date_to?: string;
    contract_year_from?: number;
    contract_year_to?: number;
  },
): Promise<CommercialRegressionPredictResponse> {
  const { data } = await api.post<CommercialRegressionPredictResponse>("/analysis/cohort/regression/predict", {
    cluster_keys: body.cluster_keys,
    asset_type: body.asset_type,
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
    model_type: body.model_type,
    contract_date_from: body.contract_date_from,
    contract_date_to: body.contract_date_to,
    contract_year_from: body.contract_year_from,
    contract_year_to: body.contract_year_to,
    inputs: body.inputs,
  });
  return data;
}

export async function fetchCommercialCohortHistogram(
  body: {
    cluster_keys: string[];
    asset_type?: CommercialAssetType;
    contract_date_from?: string;
    contract_date_to?: string;
    contract_year_from?: number;
    contract_year_to?: number;
  },
  params?: { bins?: number; contract_year?: number },
): Promise<CommercialCohortHistogramResponse> {
  const { data } = await api.post<CommercialCohortHistogramResponse>("/analysis/cohort/histogram", body, {
    params,
  });
  return data;
}

export async function fetchCommercialCohortTransactions(
  body: {
    cluster_keys: string[];
    asset_type?: CommercialAssetType;
    contract_date_from?: string;
    contract_date_to?: string;
    contract_year_from?: number;
    contract_year_to?: number;
    page?: number;
    page_size?: number;
    contract_year?: number;
  },
): Promise<CommercialCohortTransactionsResponse> {
  const { data } = await api.post<CommercialCohortTransactionsResponse>("/analysis/cohort/transactions", body);
  return data;
}

export async function downloadCommercialCohortTransactionsCsv(body: {
  cluster_keys: string[];
  asset_type?: CommercialAssetType;
  contract_date_from?: string;
  contract_date_to?: string;
  contract_year_from?: number;
  contract_year_to?: number;
}): Promise<void> {
  const response = await api.post<Blob>("/analysis/cohort/transactions/export", body, {
    responseType: "blob",
  });
  saveBlobAsFile(
    response.data,
    filenameFromContentDisposition(response.headers["content-disposition"], "cohort_transactions.csv"),
  );
}

export async function fetchCommercialPeerClusters(
  clusterKey: string,
  params?: ClusterScopeParams,
): Promise<CommercialPeerClusterListResponse> {
  const { data } = await api.get<CommercialPeerClusterListResponse>(`/clusters/${clusterKey}/peer-clusters`, {
    params,
    paramsSerializer: { indexes: null },
  });
  return data;
}

export async function runCommercialCohortFloorIndex(body: {
  cluster_keys: string[];
  asset_type?: CommercialAssetType;
  dimension?: "floor" | "area";
  experiment?: boolean;
  contract_date_from?: string;
  contract_date_to?: string;
  contract_year_from?: number;
  contract_year_to?: number;
}): Promise<CommercialCohortFloorIndexResponse> {
  const { data } = await api.post<CommercialCohortFloorIndexResponse>("/analysis/cohort/floor-index", body);
  return data;
}

export async function runCommercialCohortRegression(body: {
  cluster_keys: string[];
  asset_type?: CommercialAssetType;
  exclude_outliers_iqr?: boolean;
  experiment?: boolean;
  model_type?: "log" | "linear";
  variables?: Parameters<typeof runCommercialRegression>[1]["variables"];
  contract_date_from?: string;
  contract_date_to?: string;
  contract_year_from?: number;
  contract_year_to?: number;
}): Promise<CommercialCohortRegressionResponse> {
  const { data } = await api.post<CommercialCohortRegressionResponse>("/analysis/cohort/regression/run", {
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
    model_type: body.model_type,
    cluster_keys: body.cluster_keys,
    asset_type: body.asset_type,
    contract_date_from: body.contract_date_from,
    contract_date_to: body.contract_date_to,
    contract_year_from: body.contract_year_from,
    contract_year_to: body.contract_year_to,
  });
  return data;
}
