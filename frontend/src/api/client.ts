import axios from "axios";
import type {
  FreeStatsV2Response,
  FreeStatsWindowYears,
  LandRegressionPredictRequest,
  LandRegressionPredictResponse,
  LandRegressionRequest,
  LandRegressionResponse,
  LandRegressionSuggestResponse,
  MatrixCellHistogramRequest,
  MatrixCellHistogramResponse,
  MatrixCellTransactionsRequest,
  MatrixCellTransactionsResponse,
  MatrixYearlyRequest,
  MatrixYearlyResponse,
  LongTermTrendRequest,
  LongTermTrendResponse,
  PaidAnalysisRequest,
  PaidAnalysisResponse,
  RegionItem,
  RegionLevel,
  ProfileSigunguTwinsResponse,
  TwinNeighborsForEupmyeondongResponse,
  TwinNeighborsForSigunguResponse,
  TwinRegionLatestBatch,
  TwinV8NeighborsResponse,
  TwinV8RegionLevel,
  UpperStatsV2Response,
} from "../types";
import { normalizeFreeStatsWindowYears } from "../types";
import { DEFAULT_PROFILE_VERSION, FALLBACK_PROFILE_VERSION } from "../constants/profileVersion";
import { filenameFromContentDisposition, saveBlobAsFile } from "../utils/downloadBlob";
import { viteOptionalV2AsOfMonth } from "../utils/freeStatsV2";

/**
 * DECISIONS D-007 — 빌드 시 `VITE_API_TOKEN` 이 주입돼 있으면 모든 API 호출에 `X-Api-Token` 헤더를 단다.
 * 값이 없으면 헤더를 보내지 않아 개발 모드(미설정 백엔드)와 호환.
 */
const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();
const api = axios.create({
  baseURL: "/api",
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

/** 전체 카탈로그: limit 미지정·비검색 시 4만 행 규모 로드(search 시 서버에서 짧게 캡). */
export const fetchRegions = async (params?: {
  sigungu_code?: string;
  eupmyeondong_code?: string;
  search?: string;
  limit?: number;
}): Promise<RegionItem[]> => {
  const p: Record<string, string | number> = params ? { ...params } : {};
  const hasSearch = Boolean(params?.search && params.search.trim().length > 0);
  if (!hasSearch && p.limit === undefined) {
    p.limit = 50000;
  }
  const { data } = await api.get<RegionItem[]>("/free/v2/regions", { params: p });
  return data;
};

export const fetchFreeStats = async (
  beopjungri_code: string,
  opts: {
    window_years: FreeStatsWindowYears | unknown;
    matrix_mode?: "category" | "group";
  }
): Promise<FreeStatsV2Response> => {
  const w = normalizeFreeStatsWindowYears(opts.window_years);
  const asOf = viteOptionalV2AsOfMonth();
  const qs = new URLSearchParams({ window_years: String(w) });
  if (asOf) qs.set("as_of_month", asOf);
  if (opts.matrix_mode && opts.matrix_mode !== "category") {
    qs.set("matrix_mode", opts.matrix_mode);
  }
  const { data } = await api.get<FreeStatsV2Response>(
    `/free/v2/stats/${encodeURIComponent(beopjungri_code)}?${qs.toString()}`
  );
  return data;
};
/** 복수 법정동·리 합산 (유료 모드 기본 통계 등) — V2 동일 period 원장 재집계 */
export const fetchFreeStatsBulk = async (
  region_codes: string[],
  opts: {
    window_years: FreeStatsWindowYears | unknown;
    matrix_mode?: "category" | "group";
  }
): Promise<FreeStatsV2Response> => {
  const window_years = normalizeFreeStatsWindowYears(opts.window_years);
  const asOf = viteOptionalV2AsOfMonth();
  const { data } = await api.post<FreeStatsV2Response>("/free/v2/stats/bulk", {
    region_codes,
    window_years,
    ...(asOf ? { as_of_month: asOf } : {}),
    ...(opts.matrix_mode ? { matrix_mode: opts.matrix_mode } : {}),
  });
  return data;
};
export const runPaidAnalysis = async (
  req: PaidAnalysisRequest
): Promise<PaidAnalysisResponse> => {
  const { data } = await api.post<PaidAnalysisResponse>(
    `/paid/analyze`,
    req,
    { timeout: 240000 }
  );
  return data;
};

export const fetchPaidMatrixYearly = async (
  body: MatrixYearlyRequest
): Promise<MatrixYearlyResponse> => {
  const { data } = await api.post<MatrixYearlyResponse>(
    "/paid/matrix-yearly",
    body
  );
  return data;
};

export const fetchLongTermTrend = async (
  body: LongTermTrendRequest
): Promise<LongTermTrendResponse> => {
  const { data } = await api.post<LongTermTrendResponse>(
    "/paid/long-term-trend",
    body
  );
  return data;
};

export const fetchMatrixCellHistogram = async (
  body: MatrixCellHistogramRequest
): Promise<MatrixCellHistogramResponse> => {
  const { data } = await api.post<MatrixCellHistogramResponse>(
    "/paid/matrix-cell-histogram",
    body
  );
  return data;
};

export const fetchMatrixCellTransactions = async (
  body: MatrixCellTransactionsRequest
): Promise<MatrixCellTransactionsResponse> => {
  const { data } = await api.post<MatrixCellTransactionsResponse>(
    "/paid/matrix-cell-transactions",
    body
  );
  return data;
};

/** 거래목록·집계 탭: 클라이언트 필터/피벗용 bulk 로드 (서버 limit 상한). */
const MATRIX_TX_BULK_MAX = 10_000;

/**
 * 매트릭스 칸 거래 전량 로드 — 최대 2회 API 호출.
 * 1) total 확인 2) limit=min(total, BULK_MAX) 한 번에 fetch
 */
export async function fetchAllMatrixCellTransactions(
  body: MatrixCellTransactionsRequest
): Promise<MatrixCellTransactionsResponse> {
  const probe = await fetchMatrixCellTransactions({
    ...body,
    offset: 0,
    limit: 1,
  });
  const total = probe.total;
  if (total <= 0) {
    return { ...probe, items: [], offset: 0, limit: 0 };
  }
  const bulkLimit = Math.min(total, MATRIX_TX_BULK_MAX);
  const bulk = await fetchMatrixCellTransactions({
    ...body,
    offset: 0,
    limit: bulkLimit,
  });
  return {
    ...bulk,
    total,
    offset: 0,
    limit: bulk.items.length,
  };
};

export const fetchLandRegression = async (
  body: LandRegressionRequest
): Promise<LandRegressionResponse> => {
  const { data } = await api.post<LandRegressionResponse>(
    "/paid/matrix-cell-transactions/regression",
    body
  );
  return data;
};

export const fetchLandRegressionSuggestion = async (
  body: LandRegressionRequest
): Promise<LandRegressionSuggestResponse> => {
  const { data } = await api.post<LandRegressionSuggestResponse>(
    "/paid/matrix-cell-transactions/regression/suggest",
    body
  );
  return data;
};

export const fetchLandRegressionPredict = async (
  body: LandRegressionPredictRequest
): Promise<LandRegressionPredictResponse> => {
  const { data } = await api.post<LandRegressionPredictResponse>(
    "/paid/matrix-cell-transactions/regression/predict",
    body
  );
  return data;
};

/** 매트릭스 칸 원거래 목록 CSV(UTF-8 BOM) 다운로드 — 목록 API와 동일 필터·이상치 정책 */
export const downloadMatrixCellTransactionsCsv = async (
  body: MatrixYearlyRequest,
): Promise<void> => {
  const response = await api.post<Blob>(
    "/paid/matrix-cell-transactions/export",
    body,
    { responseType: "blob" },
  );
  const filename = filenameFromContentDisposition(
    response.headers["content-disposition"],
    "matrix_transactions.csv",
  );
  saveBlobAsFile(response.data, filename);
};

/**
 * 상위 행정구역(시도·시군구·읍면동) 사전집계 단건 조회.
 * 설계: docs/UPPER_STATS_DESIGN.md / DECISIONS D-009.
 */
export const fetchUpperStats = async (
  level: RegionLevel,
  code: string,
  opts: {
    window_years: FreeStatsWindowYears | unknown;
    zone_type?: string;
    land_category?: string;
    matrix_mode?: "category" | "group";
  }
): Promise<UpperStatsV2Response> => {
  const w = normalizeFreeStatsWindowYears(opts.window_years);
  const asOf = viteOptionalV2AsOfMonth();
  const qs = new URLSearchParams({ window_years: String(w) });
  if (opts.zone_type) qs.set("zone_type", opts.zone_type);
  if (opts.land_category) qs.set("land_category", opts.land_category);
  if (opts.matrix_mode && opts.matrix_mode !== "category") {
    qs.set("matrix_mode", opts.matrix_mode);
  }
  if (asOf) qs.set("as_of_month", asOf);
  const { data } = await api.get<UpperStatsV2Response>(
    `/paid/upper-stats/${encodeURIComponent(level)}/${encodeURIComponent(code)}?${qs.toString()}`
  );
  return data;
};

/** 쌍둥이 지역 MVP — 최신 배치 메타 */
export const fetchTwinRegionLatestBatch = async (): Promise<TwinRegionLatestBatch> => {
  const { data } = await api.get<TwinRegionLatestBatch>("/twin-regions/latest-batch");
  return data;
};

/** 쌍둥이 지역 MVP — 시군구 코드 기준 유사 시군구 상위 목록 */
export const fetchTwinNeighborsForSigungu = async (
  sigunguCode: string,
): Promise<TwinNeighborsForSigunguResponse> => {
  const { data } = await api.get<TwinNeighborsForSigunguResponse>(
    `/twin-regions/neighbors/${encodeURIComponent(sigunguCode)}`,
  );
  return data;
};

/** 쌍둥이 지역 MVP — 읍면동(8자리) 기준 유사 읍면동 상위 목록 */
export const fetchTwinNeighborsForEupmyeondong = async (
  eupmyeondongCode: string,
): Promise<TwinNeighborsForEupmyeondongResponse> => {
  const { data } = await api.get<TwinNeighborsForEupmyeondongResponse>(
    `/twin-regions/eupmyeondong/neighbors/${encodeURIComponent(eupmyeondongCode)}`,
  );
  return data;
};

/** Twin v8 — 충청권 쌍둥이 (algorithm_version=8) */
export const fetchTwinV8Neighbors = async (params: {
  region_level: TwinV8RegionLevel;
  region_code: string;
  top_k?: number;
}): Promise<TwinV8NeighborsResponse> => {
  const level = params.region_level;
  const code = params.region_code.trim();
  const qs = new URLSearchParams();
  if (params.top_k != null) qs.set("top_k", String(params.top_k));
  const suffix = qs.size > 0 ? `?${qs.toString()}` : "";
  const { data } = await api.get<TwinV8NeighborsResponse>(
    `/twin-v8/neighbors/${encodeURIComponent(level)}/${encodeURIComponent(code)}${suffix}`,
  );
  return data;
};

/** 시군구 hybrid 쌍둥이(algo 7) — /regional-profile/twins-sigungu, 전국 scope 기본 */
export const fetchProfileTwinSigungu = async (params: {
  sigungu_code: string;
  profile_version?: string;
  window_years?: number;
  top_k?: number;
  scope?: "adjacent" | "region" | "national";
}): Promise<ProfileSigunguTwinsResponse> => {
  const code = params.sigungu_code.trim().slice(0, 5);
  const scope = params.scope ?? "national";
  const versions = [
    params.profile_version ?? DEFAULT_PROFILE_VERSION,
    FALLBACK_PROFILE_VERSION,
  ].filter((v, i, a) => a.indexOf(v) === i);

  let last: ProfileSigunguTwinsResponse | null = null;
  for (const pv of versions) {
    try {
      const { data } = await api.get<ProfileSigunguTwinsResponse>(
        `/regional-profile/twins-sigungu/${encodeURIComponent(code)}`,
        {
          params: {
            profile_version: pv,
            window_years: params.window_years,
            top_k: params.top_k ?? 10,
            scope,
          },
        }
      );
      last = data;
      if (data.neighbors.length > 0) return data;
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 404) continue;
      throw err;
    }
  }
  return last ?? {
    profile_version: versions[0]!,
    window_years: params.window_years ?? 5,
    scope,
    anchor_sigungu_code: code,
    neighbors: [],
  };
};
