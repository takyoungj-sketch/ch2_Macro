import axios from "axios";
import type {
  CommercialAssetSelectorType,
  CommercialAssetType,
  CommercialAddressListResponse,
  CommercialClusterListResponse,
  CommercialCohortHistogramResponse,
  CommercialCohortRegressionResponse,
  CommercialCohortTransactionsResponse,
  CommercialCohortYearlyStatsResponse,
  CommercialFilterMeta,
  CommercialFloorIndexResponse,
  CommercialHistogramResponse,
  CommercialRegressionPredictInputs,
  CommercialRegressionPredictResponse,
  CommercialRegressionResponse,
  CommercialRollingStatsResponse,
  CommercialTransactionListResponse,
  CommercialYearlyStatsResponse,
  RegressionModelType,
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
  assetType?: CommercialAssetSelectorType,
  period?: {
    contract_year_from?: number;
    contract_year_to?: number;
    contract_date_from?: string;
    contract_date_to?: string;
    window_years?: number;
  },
): Promise<RegionOption[]> {
  const { data } = await api.get<RegionOption[]>("/regions/addr3", {
    params: {
      addr1,
      addr2,
      asset_type: apiCommercialAssetParam(assetType),
      ...period,
    },
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
  period?: {
    contract_year_from?: number;
    contract_year_to?: number;
    contract_date_from?: string;
    contract_date_to?: string;
    window_years?: number;
  },
): Promise<RegionOption[]> {
  const { data } = await api.get<RegionOption[]>("/regions/leaf", {
    params: {
      addr1,
      addr2,
      asset_type: apiCommercialAssetParam(assetType),
      addr3_list: addr3List.length ? addr3List : undefined,
      ...period,
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
  const { asset_type, ...rest } = params;
  const { data } = await api.get<CommercialClusterListResponse>("/clusters", {
    params: {
      ...rest,
      asset_type: apiCommercialAssetParam(asset_type),
    },
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
    contract_date_from?: string;
    contract_date_to?: string;
    window_years?: number;
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

const COMMERCIAL_TX_FETCH_PAGE = 200;
const COMMERCIAL_TX_LOAD_CAP = 5000;

/** 거래목록 탭: 필터·정렬용 전체 로드 */
export async function fetchAllCommercialTransactions(
  clusterKey: string,
  params?: Omit<Parameters<typeof fetchCommercialTransactions>[1], "page" | "page_size">,
): Promise<CommercialTransactionListResponse & { truncated?: boolean }> {
  const first = await fetchCommercialTransactions(clusterKey, {
    ...params,
    page: 1,
    page_size: COMMERCIAL_TX_FETCH_PAGE,
  });
  if (first.total <= first.items.length || first.items.length >= COMMERCIAL_TX_LOAD_CAP) {
    return { ...first, truncated: first.total > first.items.length };
  }
  const all = [...first.items];
  let page = 2;
  while (all.length < first.total && all.length < COMMERCIAL_TX_LOAD_CAP) {
    const next = await fetchCommercialTransactions(clusterKey, {
      ...params,
      page,
      page_size: COMMERCIAL_TX_FETCH_PAGE,
    });
    all.push(...next.items);
    if (next.items.length === 0) break;
    page += 1;
  }
  return {
    ...first,
    items: all,
    truncated: all.length < first.total,
  };
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
  params?: ClusterScopeParams & {
    dimension?: "floor" | "area";
    floor_mode?: "relative" | "dummy" | "grouped";
    experiment?: boolean;
  },
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
    model_type?: RegressionModelType;
    variables?: {
      gross_area?: boolean;
      building_age?: boolean;
      floor?: boolean;
      zone_type?: boolean;
      building_use?: boolean;
      road_width?: boolean;
      road_code?: boolean;
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
    model_type: body.model_type ?? "linear",
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

export async function predictCommercialRegression(
  clusterKey: string,
  body: ClusterScopeParams & {
    exclude_outliers_iqr?: boolean;
    experiment?: boolean;
    model_type?: RegressionModelType;
    inputs: CommercialRegressionPredictInputs;
    variables?: {
      gross_area?: boolean;
      building_age?: boolean;
      floor?: boolean;
      zone_type?: boolean;
      building_use?: boolean;
      road_width?: boolean;
      road_code?: boolean;
      floor_mode?: "linear" | "dummy" | "grouped" | "relative";
    };
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
      model_type: body.model_type ?? "linear",
      exclude_outliers_iqr: body.exclude_outliers_iqr ?? false,
      experiment: body.experiment ?? false,
      inputs: body.inputs,
      addr1: body.addr1,
      addr2: body.addr2,
      addr3_list: body.addr3_list,
      addr4_list: body.addr4_list,
      contract_year_from: body.contract_year_from,
      contract_year_to: body.contract_year_to,
    },
  );
  return data;
}

type CommercialCohortBody = {
  cluster_keys: string[];
  asset_type?: CommercialAssetType;
  contract_year_from?: number;
  contract_year_to?: number;
  contract_date_from?: string;
  contract_date_to?: string;
  experiment?: boolean;
};

export async function fetchCommercialRollingStats(
  clusterKey: string,
  windowYears: number,
): Promise<CommercialRollingStatsResponse> {
  const { data } = await api.get<CommercialRollingStatsResponse>(`/clusters/${clusterKey}/stats/rolling`, {
    params: { window_years: windowYears },
  });
  return data;
}

export async function runCommercialCohortFloorIndex(
  body: CommercialCohortBody & {
    dimension?: "floor" | "area";
    variables?: { floor_mode?: string };
  },
): Promise<CommercialFloorIndexResponse> {
  const { data } = await api.post<CommercialFloorIndexResponse>("/analysis/cohort/floor-index", body);
  return data;
}

export async function fetchCommercialCohortYearlyStats(
  body: CommercialCohortBody,
): Promise<CommercialCohortYearlyStatsResponse> {
  const { data } = await api.post<CommercialCohortYearlyStatsResponse>("/analysis/cohort/stats/by-year", body);
  return data;
}

export async function fetchCommercialCohortHistogram(
  body: CommercialCohortBody,
  params?: { bins?: number; contract_year?: number },
): Promise<CommercialCohortHistogramResponse> {
  const { data } = await api.post<CommercialCohortHistogramResponse>("/analysis/cohort/histogram", body, { params });
  return data;
}

export async function fetchCommercialCohortTransactions(
  body: CommercialCohortBody & { page?: number; page_size?: number; contract_year?: number },
): Promise<CommercialCohortTransactionsResponse> {
  const { data } = await api.post<CommercialCohortTransactionsResponse>("/analysis/cohort/transactions", body);
  return data;
}

/** 코호트 거래목록 탭: 필터·정렬용 전체 로드 */
export async function fetchAllCommercialCohortTransactions(
  body: CommercialCohortBody & { contract_year?: number },
): Promise<CommercialCohortTransactionsResponse & { truncated?: boolean }> {
  const first = await fetchCommercialCohortTransactions({
    ...body,
    page: 1,
    page_size: COMMERCIAL_TX_FETCH_PAGE,
  });
  if (first.total <= first.items.length || first.items.length >= COMMERCIAL_TX_LOAD_CAP) {
    return { ...first, truncated: first.total > first.items.length };
  }
  const all = [...first.items];
  let page = 2;
  while (all.length < first.total && all.length < COMMERCIAL_TX_LOAD_CAP) {
    const next = await fetchCommercialCohortTransactions({
      ...body,
      page,
      page_size: COMMERCIAL_TX_FETCH_PAGE,
    });
    all.push(...next.items);
    if (next.items.length === 0) break;
    page += 1;
  }
  return {
    ...first,
    items: all,
    truncated: all.length < first.total,
  };
}

export async function runCommercialCohortRegression(
  body: CommercialCohortBody & {
    exclude_outliers_iqr?: boolean;
    model_type?: RegressionModelType;
    variables?: Record<string, unknown>;
  },
): Promise<CommercialCohortRegressionResponse> {
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
    model_type: body.model_type ?? "linear",
    exclude_outliers_iqr: body.exclude_outliers_iqr ?? false,
    experiment: body.experiment ?? false,
    cluster_keys: body.cluster_keys,
    asset_type: body.asset_type,
    contract_year_from: body.contract_year_from,
    contract_year_to: body.contract_year_to,
    contract_date_from: body.contract_date_from,
    contract_date_to: body.contract_date_to,
  });
  return data;
}

export async function predictCommercialCohortRegression(
  body: CommercialCohortBody & {
    exclude_outliers_iqr?: boolean;
    model_type?: RegressionModelType;
    inputs: CommercialRegressionPredictInputs;
    variables?: Record<string, unknown>;
  },
): Promise<CommercialRegressionPredictResponse> {
  const { data } = await api.post<CommercialRegressionPredictResponse>("/analysis/cohort/regression/predict", {
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
    model_type: body.model_type ?? "linear",
    exclude_outliers_iqr: body.exclude_outliers_iqr ?? false,
    experiment: body.experiment ?? false,
    inputs: body.inputs,
    cluster_keys: body.cluster_keys,
    asset_type: body.asset_type,
    contract_year_from: body.contract_year_from,
    contract_year_to: body.contract_year_to,
    contract_date_from: body.contract_date_from,
    contract_date_to: body.contract_date_to,
  });
  return data;
}
