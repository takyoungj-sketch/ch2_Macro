import axios from "axios";
import type {
  FreeStatsResponse,
  MatrixYearlyRequest,
  MatrixYearlyResponse,
  PaidAnalysisRequest,
  PaidAnalysisResponse,
  RegionItem,
} from "../types";

const api = axios.create({ baseURL: "/api" });

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
    p.limit = 40000;
  }
  const { data } = await api.get<RegionItem[]>("/free/regions", { params: p });
  return data;
};

export const fetchFreeStats = async (
  beopjungri_code: string
): Promise<FreeStatsResponse> => {
  const { data } = await api.get<FreeStatsResponse>(
    `/free/stats/${beopjungri_code}`
  );
  return data;
};

/** 복수 법정동·리 합산 (유료 모드 기본 통계 등) */
export const fetchFreeStatsBulk = async (
  region_codes: string[]
): Promise<FreeStatsResponse> => {
  const { data } = await api.post<FreeStatsResponse>("/free/stats/bulk", {
    region_codes,
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
