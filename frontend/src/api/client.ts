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

export const fetchRegions = async (params?: {
  sigungu_code?: string;
  eupmyeondong_code?: string;
}): Promise<RegionItem[]> => {
  const { data } = await api.get<RegionItem[]>("/free/regions", { params });
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
