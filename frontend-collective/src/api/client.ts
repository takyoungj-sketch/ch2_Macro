/** 실험 단계: 분석 게이트 우회 + 모든 탭·옵션 항상 사용 (운영 전 false) */
export const COLLECTIVE_EXPERIMENT_MODE =
  import.meta.env.VITE_COLLECTIVE_EXPERIMENT === "true" || import.meta.env.DEV;

import axios from "axios";
import { filenameFromContentDisposition, saveBlobAsFile } from "../utils/downloadBlob";
import type {
  AssetType,
  AssetSelectorType,
  BuildingListResponse,
  BuildingStatsRow,
  CollectiveFilterMeta,
  CohortFloorIndexResponse,
  CohortHistogramResponse,
  CohortRegressionResponse,
  CohortTransactionsResponse,
  CohortYearlyStatsResponse,
  CollectiveRegressionPredictInputs,
  CollectiveRegressionPredictResponse,
  CollectiveRegressionResponse,
  CollectiveTransactionRow,
  DanjiAttributesResponse,
  FloorIndexResponse,
  HistogramResponse,
  RegionOption,
  RegionStructure,
  RollingStatsResponse,
  YearlyStatPoint,
  YearlyStatsResponse,
} from "../types";

const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();
const api = axios.create({
  baseURL: "/api/collective",
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

function apiAssetParam(assetType?: AssetSelectorType): string | undefined {
  if (!assetType || assetType === "all") return undefined;
  return assetType;
}

export async function fetchFilterMeta(assetType?: AssetSelectorType): Promise<CollectiveFilterMeta> {
  const { data } = await api.get<CollectiveFilterMeta>("/meta/filters", {
    params: apiAssetParam(assetType) ? { asset_type: apiAssetParam(assetType) } : undefined,
  });
  return data;
}

/** 시도 목록 — region_codes SSOT (meta/filters 대기 없이 즉시 표시). */
export async function fetchAddr1List(): Promise<string[]> {
  const { data } = await api.get<string[]>("/regions/addr1");
  return data;
}

export async function fetchAddr2(addr1: string, assetType?: AssetSelectorType): Promise<string[]> {
  const { data } = await api.get<string[]>("/regions/addr2", {
    params: { addr1, asset_type: apiAssetParam(assetType) },
  });
  return data;
}

export async function fetchRegionStructure(
  addr1: string,
  addr2: string,
  assetType?: AssetSelectorType,
): Promise<RegionStructure> {
  const { data } = await api.get<RegionStructure>("/regions/structure", {
    params: { addr1, addr2, asset_type: apiAssetParam(assetType) },
  });
  return data;
}

export async function fetchAddr3WithCounts(
  addr1: string,
  addr2: string,
  assetType?: AssetSelectorType,
  period?: {
    contract_year_from?: number;
    contract_year_to?: number;
  },
): Promise<RegionOption[]> {
  const { data } = await api.get<RegionOption[]>("/regions/addr3", {
    params: { addr1, addr2, asset_type: apiAssetParam(assetType), ...period },
  });
  return data;
}

export async function fetchLeafRegions(
  addr1: string,
  addr2: string,
  addr3List: string[],
  assetType?: AssetSelectorType,
  period?: {
    contract_year_from?: number;
    contract_year_to?: number;
  },
): Promise<RegionOption[]> {
  const { data } = await api.get<RegionOption[]>("/regions/leaf", {
    params: {
      addr1,
      addr2,
      asset_type: apiAssetParam(assetType),
      addr3_list: addr3List.length ? addr3List : undefined,
      ...period,
    },
    paramsSerializer: { indexes: null },
  });
  return data;
}

export async function fetchBuildings(params: {
  asset_type?: AssetSelectorType;
  addr1?: string;
  addr2?: string;
  addr3_list?: string[];
  addr4_list?: string[];
  contract_year_from?: number;
  contract_year_to?: number;
  window_years?: number;
  /** 분양권: rolling(기본·3/5년) | lifetime(전체기간 보조) */
  presale_stats_mode?: "lifetime" | "rolling";
  sort?: string;
  page?: number;
  page_size?: number;
}): Promise<BuildingListResponse> {
  const { data } = await api.get<BuildingListResponse>("/buildings", {
    params: {
      ...params,
      asset_type: params.asset_type === "all" ? "all" : params.asset_type,
    },
    paramsSerializer: { indexes: null },
  });
  return data;
}

/** API page_size 상한(500)을 넘는 목록을 모두 조회 */
export async function fetchAllBuildings(
  params: Omit<Parameters<typeof fetchBuildings>[0], "page" | "page_size">,
): Promise<BuildingListResponse> {
  const pageSize = 500;
  let page = 1;
  let meta: BuildingListResponse | null = null;
  const items: BuildingListResponse["items"] = [];

  while (true) {
    const batch = await fetchBuildings({ ...params, page, page_size: pageSize });
    if (!meta) meta = batch;
    items.push(...batch.items);
    if (items.length >= batch.total || batch.items.length < pageSize) {
      return { ...(meta ?? batch), items, total: batch.total };
    }
    page += 1;
  }
}

export async function fetchBuildingTransactions(
  buildingKey: string,
  params?: {
    contract_year_from?: number;
    contract_year_to?: number;
    contract_date_from?: string;
    contract_date_to?: string;
    page?: number;
    page_size?: number;
  },
): Promise<{ total: number; items: CollectiveTransactionRow[] }> {
  const { data } = await api.get(`/buildings/${buildingKey}/transactions`, { params });
  return data;
}

const COLLECTIVE_TX_FETCH_PAGE = 200;
const COLLECTIVE_TX_LOAD_CAP = 5000;

/** 거래목록 탭: 필터·정렬용 전체 로드 (API page_size 상한 200). */
export async function fetchAllBuildingTransactions(
  buildingKey: string,
  params?: Omit<Parameters<typeof fetchBuildingTransactions>[1], "page" | "page_size">,
): Promise<{ total: number; items: CollectiveTransactionRow[]; truncated?: boolean }> {
  const first = await fetchBuildingTransactions(buildingKey, {
    ...params,
    page: 1,
    page_size: COLLECTIVE_TX_FETCH_PAGE,
  });
  if (first.total <= first.items.length || first.items.length >= COLLECTIVE_TX_LOAD_CAP) {
    return { ...first, truncated: first.total > first.items.length };
  }
  const all = [...first.items];
  let page = 2;
  while (all.length < first.total && all.length < COLLECTIVE_TX_LOAD_CAP) {
    const next = await fetchBuildingTransactions(buildingKey, {
      ...params,
      page,
      page_size: COLLECTIVE_TX_FETCH_PAGE,
    });
    all.push(...next.items);
    if (next.items.length === 0) break;
    page += 1;
  }
  return {
    total: first.total,
    items: all,
    truncated: all.length < first.total,
  };
}

/** 거래목록 CSV(UTF-8 BOM) — 목록 API와 동일 필터·전체 건 */
export async function downloadBuildingTransactionsCsv(
  buildingKey: string,
  params?: {
    contract_year_from?: number;
    contract_year_to?: number;
    contract_date_from?: string;
    contract_date_to?: string;
  },
): Promise<void> {
  const response = await api.get<Blob>(`/buildings/${buildingKey}/transactions/export`, {
    params,
    responseType: "blob",
  });
  const filename = filenameFromContentDisposition(
    response.headers["content-disposition"],
    "transactions.csv",
  );
  saveBlobAsFile(response.data, filename);
}

export async function fetchBuildingHistogram(
  buildingKey: string,
  params?: {
    contract_year?: number;
    bins?: number;
    contract_date_from?: string;
    contract_date_to?: string;
  },
): Promise<HistogramResponse> {
  const { data } = await api.get<HistogramResponse>(`/buildings/${buildingKey}/histogram`, { params });
  return data;
}

export async function fetchBuildingYearlyStats(
  buildingKey: string,
  params?: { contract_date_from?: string; contract_date_to?: string },
): Promise<YearlyStatsResponse> {
  const { data } = await api.get<YearlyStatsResponse>(`/buildings/${buildingKey}/stats/by-year`, { params });
  return data;
}

export type RelatedPresaleCandidate = {
  building_key: string;
  display_name: string;
  addr1?: string | null;
  addr2?: string | null;
  addr3?: string | null;
  addr4?: string | null;
  year_from: number;
  year_to: number;
  total_count: number;
  score: number;
};

export type RelatedPresaleResponse = {
  source_building_key: string;
  source_display_name: string;
  source_asset_type: string;
  candidates: RelatedPresaleCandidate[];
};

export async function fetchRelatedPresaleAnnual(
  buildingKey: string,
  params?: { limit?: number; min_score?: number },
): Promise<RelatedPresaleResponse> {
  const { data } = await api.get<RelatedPresaleResponse>(`/buildings/${buildingKey}/related-presale`, {
    params,
  });
  return data;
}

export async function fetchBuildingRollingStats(
  buildingKey: string,
  windowYears: number,
): Promise<RollingStatsResponse> {
  const { data } = await api.get<RollingStatsResponse>(`/buildings/${buildingKey}/stats/rolling`, {
    params: { window_years: windowYears },
  });
  return data;
}

/** K-apt 단지 속성 (실험) — 미매칭도 200 + 사유로 응답한다. */
export async function fetchDanjiAttributes(buildingKey: string): Promise<DanjiAttributesResponse> {
  const { data } = await api.get<DanjiAttributesResponse>(
    `/buildings/${buildingKey}/danji-attributes`,
  );
  return data;
}

export async function runCohortFloorIndex(body: {
  building_keys: string[];
  asset_type?: AssetType;
  contract_year_from?: number;
  contract_year_to?: number;
  contract_date_from?: string;
  contract_date_to?: string;
  dimension?: "floor" | "dong" | "area" | "rights";
  variables?: { floor_mode?: "relative" | "dummy" | "grouped" | "linear" };
  experiment?: boolean;
}): Promise<CohortFloorIndexResponse> {
  const { data } = await api.post<CohortFloorIndexResponse>("/analysis/cohort/floor-index", {
    ...body,
    variables: {
      floor_mode: body.variables?.floor_mode ?? "relative",
    },
  });
  return data;
}

export async function runCohortRegression(body: {
  building_keys: string[];
  asset_type?: AssetType;
  contract_year_from?: number;
  contract_year_to?: number;
  contract_date_from?: string;
  contract_date_to?: string;
  experiment?: boolean;
  exclude_outliers_iqr?: boolean;
  model_type?: "log" | "linear";
  variables?: {
    exclusive_area?: boolean;
    building_age?: boolean;
    floor?: boolean;
    dong?: boolean;
    housing_subtype?: boolean;
    floor_mode?: "linear" | "dummy" | "grouped" | "relative";
  };
}): Promise<CohortRegressionResponse> {
  const { data } = await api.post<CohortRegressionResponse>("/analysis/cohort/regression/run", {
    variables: {
      exclusive_area: true,
      building_age: true,
      floor: true,
      dong: true,
      floor_mode: "relative",
      ...body.variables,
    },
    ...body,
  });
  return data;
}

type RegressionBody = {
  asset_type?: AssetType;
  contract_year_from?: number;
  contract_year_to?: number;
  contract_date_from?: string;
  contract_date_to?: string;
  experiment?: boolean;
  exclude_outliers_iqr?: boolean;
  model_type?: "log" | "linear";
  variables?: {
    exclusive_area?: boolean;
    building_age?: boolean;
    floor?: boolean;
    dong?: boolean;
    housing_subtype?: boolean;
    floor_mode?: "linear" | "dummy" | "grouped" | "relative";
  };
};

export async function predictBuildingRegression(
  buildingKey: string,
  body: RegressionBody & { inputs: CollectiveRegressionPredictInputs },
): Promise<CollectiveRegressionPredictResponse> {
  const { data } = await api.post<CollectiveRegressionPredictResponse>(
    `/buildings/${buildingKey}/regression/predict`,
    {
      variables: {
        exclusive_area: true,
        building_age: true,
        floor: true,
        dong: true,
        floor_mode: "relative",
        ...body.variables,
      },
      ...body,
    },
  );
  return data;
}

export async function predictCohortRegression(
  body: RegressionBody & { building_keys: string[]; inputs: CollectiveRegressionPredictInputs },
): Promise<CollectiveRegressionPredictResponse> {
  const { data } = await api.post<CollectiveRegressionPredictResponse>("/analysis/cohort/regression/predict", {
    variables: {
      exclusive_area: true,
      building_age: true,
      floor: true,
      dong: true,
      floor_mode: "relative",
      ...body.variables,
    },
    ...body,
  });
  return data;
}

type CohortBody = {
  building_keys: string[];
  asset_type?: AssetType;
  contract_year_from?: number;
  contract_year_to?: number;
  contract_date_from?: string;
  contract_date_to?: string;
  experiment?: boolean;
};

export async function fetchCohortYearlyStats(body: CohortBody): Promise<CohortYearlyStatsResponse> {
  const { data } = await api.post<CohortYearlyStatsResponse>("/analysis/cohort/stats/by-year", body);
  return data;
}

export async function fetchCohortHistogram(
  body: CohortBody,
  params?: { bins?: number; contract_year?: number },
): Promise<CohortHistogramResponse> {
  const { data } = await api.post<CohortHistogramResponse>("/analysis/cohort/histogram", body, { params });
  return data;
}

export async function fetchCohortTransactions(
  body: CohortBody & { page?: number; page_size?: number; contract_year?: number },
): Promise<CohortTransactionsResponse> {
  const { data } = await api.post<CohortTransactionsResponse>("/analysis/cohort/transactions", body);
  return data;
}

/** 코호트 거래목록 탭: 필터·정렬용 전체 로드 */
export async function fetchAllCohortTransactions(
  body: CohortBody & { contract_year?: number },
): Promise<CohortTransactionsResponse & { truncated?: boolean }> {
  const first = await fetchCohortTransactions({
    ...body,
    page: 1,
    page_size: COLLECTIVE_TX_FETCH_PAGE,
  });
  if (first.total <= first.items.length || first.items.length >= COLLECTIVE_TX_LOAD_CAP) {
    return { ...first, truncated: first.total > first.items.length };
  }
  const all = [...first.items];
  let page = 2;
  while (all.length < first.total && all.length < COLLECTIVE_TX_LOAD_CAP) {
    const next = await fetchCohortTransactions({
      ...body,
      page,
      page_size: COLLECTIVE_TX_FETCH_PAGE,
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

/** 코호트 거래목록 CSV — 목록 API와 동일 필터·전체 건 */
export async function downloadCohortTransactionsCsv(body: CohortBody): Promise<void> {
  const response = await api.post<Blob>("/analysis/cohort/transactions/export", body, {
    responseType: "blob",
  });
  const filename = filenameFromContentDisposition(
    response.headers["content-disposition"],
    "cohort_transactions.csv",
  );
  saveBlobAsFile(response.data, filename);
}

export async function fetchBuildingFloorIndex(
  buildingKey: string,
  params?: {
    dimension?: "floor" | "dong" | "area" | "rights";
    floor_mode?: "relative" | "dummy" | "grouped" | "linear";
    contract_year_from?: number;
    contract_year_to?: number;
    contract_date_from?: string;
    contract_date_to?: string;
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
    contract_date_from?: string;
    contract_date_to?: string;
    exclude_outliers_iqr?: boolean;
    experiment?: boolean;
    model_type?: "log" | "linear";
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
