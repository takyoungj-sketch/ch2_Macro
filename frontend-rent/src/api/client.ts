import axios from "axios";
import type {
  RentAssetType,
  RentBuildingListResponse,
  RentConversionCompareRow,
  RentConversionValidateReport,
  RentRbDistributionReport,
  RentRegionOption,
  RentRegionStructure,
  RentRollingPoint,
  SangkwonAnnualResponse,
  SangkwonSeriesResponse,
  StatsWindowYears,
} from "../types";

const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();
const api = axios.create({
  baseURL: "/api/rent",
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

export async function fetchRentMeta(windowYears: StatsWindowYears) {
  const { data } = await api.get<{ addr1: string[]; as_of_month: string | null }>(
    "/meta",
    { params: { window_years: windowYears } },
  );
  return data;
}

export async function fetchAddr2(addr1: string, windowYears: StatsWindowYears) {
  const { data } = await api.get<RentRegionOption[]>("/regions/addr2", {
    params: { addr1, window_years: windowYears },
  });
  return data;
}

export async function fetchAddr3(
  addr1: string,
  addr2: string,
  windowYears: StatsWindowYears,
  assetTypes?: RentAssetType[],
) {
  const { data } = await api.get<RentRegionOption[]>("/regions/addr3", {
    params: {
      addr1,
      addr2,
      window_years: windowYears,
      asset_type: assetTypes,
    },
    paramsSerializer: { indexes: null },
  });
  return data;
}

export async function fetchRentStructure(
  addr1: string,
  addr2: string,
  windowYears: StatsWindowYears,
) {
  const { data } = await api.get<RentRegionStructure>("/regions/structure", {
    params: { addr1, addr2, window_years: windowYears },
  });
  return data;
}

export async function fetchRentLeaf(
  addr1: string,
  addr2: string,
  windowYears: StatsWindowYears,
  guList: string[],
  assetTypes?: RentAssetType[],
) {
  const { data } = await api.get<RentRegionOption[]>("/regions/leaf", {
    params: {
      addr1,
      addr2,
      window_years: windowYears,
      addr3_list: guList,
      asset_type: assetTypes,
    },
    paramsSerializer: { indexes: null },
  });
  return data;
}

export async function fetchRentBuildings(params: {
  addr1: string;
  addr2: string;
  addr3?: string;
  addr3List?: string[];
  addr4List?: string[];
  assetTypes: RentAssetType[];
  windowYears: StatsWindowYears;
  sort: string;
}) {
  const { data } = await api.get<RentBuildingListResponse>("/buildings", {
    params: {
      addr1: params.addr1,
      addr2: params.addr2,
      addr3: params.addr3 || undefined,
      addr3_list: params.addr3List,
      addr4_list: params.addr4List,
      asset_type: params.assetTypes,
      window_years: params.windowYears,
      sort: params.sort,
    },
    paramsSerializer: {
      indexes: null,
    },
  });
  return data;
}

export async function fetchConversionCompare(params: {
  addr1: string;
  assetTypes: RentAssetType[];
  windowYears?: StatsWindowYears[];
}) {
  const { data } = await api.get<{
    as_of_month: string | null;
    items: RentConversionCompareRow[];
  }>("/conversion-rates", {
    params: {
      addr1: params.addr1,
      asset_type: params.assetTypes,
      window_years: params.windowYears,
    },
    paramsSerializer: { indexes: null },
  });
  return data;
}

export async function fetchConversionValidate() {
  const { data } = await api.get<RentConversionValidateReport>("/conversion-validate");
  return data;
}

export async function fetchRbDistribution() {
  const { data } = await api.get<RentRbDistributionReport>("/rb-distribution");
  return data;
}

export async function fetchRentRolling(params: {
  buildingKey: string;
  assetType: string;
  windowYears: StatsWindowYears;
}) {
  const { data } = await api.get<{ points: RentRollingPoint[] }>(
    `/buildings/${encodeURIComponent(params.buildingKey)}/rolling`,
    { params: { asset_type: params.assetType, window_years: params.windowYears } },
  );
  return data.points;
}

export type RentTransactionRow = {
  id: number;
  contract_date: string | null;
  contract_year: number | null;
  contract_month: number | null;
  floor: number | null;
  exclusive_area: number | null;
  deposit_manwon: number | null;
  monthly_rent_manwon: number | null;
  deposit_per_m2: number | null;
  monthly_per_m2: number | null;
  lease_kind: string;
  building_year?: number | null;
};

export async function fetchRentTransactions(params: {
  buildingKey: string;
  assetType?: string;
  page?: number;
  pageSize?: number;
}) {
  const { data } = await api.get<{ total: number; items: RentTransactionRow[] }>(
    `/buildings/${encodeURIComponent(params.buildingKey)}/transactions`,
    {
      params: {
        asset_type: params.assetType,
        page: params.page ?? 1,
        page_size: params.pageSize ?? 50,
      },
    },
  );
  return data;
}

const RENT_TX_FETCH_PAGE = 200;
const RENT_TX_LOAD_CAP = 5000;

/** 거래목록 탭: 필터·정렬용 전체 로드 (API page_size 상한 200). */
export async function fetchAllRentTransactions(params: {
  buildingKey: string;
  assetType?: string;
}): Promise<{ total: number; items: RentTransactionRow[]; truncated?: boolean }> {
  const first = await fetchRentTransactions({
    ...params,
    page: 1,
    pageSize: RENT_TX_FETCH_PAGE,
  });
  if (first.total <= first.items.length || first.items.length >= RENT_TX_LOAD_CAP) {
    return { ...first, truncated: first.total > first.items.length };
  }
  const all = [...first.items];
  let page = 2;
  while (all.length < first.total && all.length < RENT_TX_LOAD_CAP) {
    const next = await fetchRentTransactions({
      ...params,
      page,
      pageSize: RENT_TX_FETCH_PAGE,
    });
    if (!next.items.length) break;
    all.push(...next.items);
    page += 1;
  }
  return { total: first.total, items: all, truncated: all.length < first.total };
}

export type RentRegressionResult = {
  building_key: string;
  display_name: string;
  n: number;
  model_type?: string;
  adj_r_squared: number | null;
  mape: number | null;
  equation?: string;
  coefficients: Array<{
    name: string;
    label?: string;
    estimate?: number;
    effect_plain?: string;
    se?: number | null;
    t?: number | null;
    p?: number | null;
    p_value?: number | null;
  }>;
  warnings?: string[];
};

function regressionAssetType(assetType: string): string {
  return assetType === "detached" ? "apartment" : assetType;
}

export async function runRentRegression(params: {
  buildingKeys: string[];
  assetType: string;
  exclusiveArea?: boolean;
  floor?: boolean;
  buildingAge?: boolean;
  modelType?: "linear" | "log";
}): Promise<RentRegressionResult> {
  const keys = params.buildingKeys.filter(Boolean);
  const body = {
    asset_type: regressionAssetType(params.assetType),
    model_type: params.modelType ?? "linear",
    variables: {
      exclusive_area: params.exclusiveArea ?? true,
      floor: params.floor ?? true,
      building_age: params.buildingAge ?? true,
    },
  };
  const query = { asset_type: params.assetType, lease_kind: "jeonse" };
  if (keys.length <= 1) {
    const { data } = await api.post<RentRegressionResult>(
      `/buildings/${encodeURIComponent(keys[0] ?? "")}/regression/run`,
      body,
      { params: query },
    );
    return data;
  }
  const { data } = await api.post<RentRegressionResult>("/regression/run", body, {
    params: { ...query, building_key: keys },
    paramsSerializer: { indexes: null },
  });
  return data;
}

export async function fetchSangkwonPolygons(sido?: string) {
  const { data } = await api.get<{
    type: string;
    features: GeoJSON.Feature[];
    latest_year: number | null;
    source_file: string;
  }>("/sangkwon/polygons", { params: sido ? { sido } : undefined });
  return data;
}

export async function fetchSangkwonAnnual(name: string, year?: number) {
  const { data } = await api.get<SangkwonAnnualResponse>("/sangkwon/annual", {
    params: { name, year },
  });
  return data;
}

export async function fetchSangkwonSeries(name: string, fromYear = 2019) {
  const { data } = await api.get<SangkwonSeriesResponse>("/sangkwon/series", {
    params: { name, from_year: fromYear },
  });
  return data;
}
