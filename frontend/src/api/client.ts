import axios from "axios";
import type {
  FreeStatsResponse,
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

export const runPaidAnalysis = async (
  req: PaidAnalysisRequest
): Promise<PaidAnalysisResponse> => {
  const { data } = await api.post<PaidAnalysisResponse>("/paid/analyze", req);
  return data;
};
