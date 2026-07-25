import { apiClient } from "./client";
import type {
  ProfileTwinNeighborsResponse,
  RegionLevel,
  RegionNameInfo,
  RegionalProfileResponse,
} from "../types";

export const DEFAULT_PROFILE_VERSION = "v2.0-national";
export const DEFAULT_WINDOW_YEARS = 3;

// 기존 Twin v6(hybrid)/v7(sigungu hybrid) 배치는 Profile v1.1-national/5y 기준으로 생성됨.
// Profile v2 검증 완료 후 Profile-native Twin으로 전환 예정(D-027 §12 phased plan) — 그 전까지 유지.
export const DEFAULT_TWIN_PROFILE_VERSION = "v1.1-national";
export const DEFAULT_TWIN_WINDOW_YEARS = 5;

export async function fetchRegionalProfile(params: {
  regionLevel: RegionLevel;
  regionCode: string;
  profileVersion?: string;
  windowYears?: number;
}): Promise<RegionalProfileResponse> {
  const { data } = await apiClient.get<RegionalProfileResponse>("/regional-profile", {
    params: {
      region_level: params.regionLevel,
      region_code: params.regionCode,
      profile_version: params.profileVersion ?? DEFAULT_PROFILE_VERSION,
      window_years: params.windowYears ?? DEFAULT_WINDOW_YEARS,
    },
  });
  return data;
}

export async function fetchTwinNeighbors(params: {
  regionLevel: RegionLevel;
  regionCode: string;
  profileVersion?: string;
  windowYears?: number;
  topK?: number;
}): Promise<ProfileTwinNeighborsResponse> {
  const path =
    params.regionLevel === "sigungu"
      ? `/regional-profile/twins-sigungu/${params.regionCode}`
      : `/regional-profile/twins/${params.regionCode}`;
  const { data } = await apiClient.get<ProfileTwinNeighborsResponse>(path, {
    params: {
      profile_version: params.profileVersion ?? DEFAULT_TWIN_PROFILE_VERSION,
      window_years: params.windowYears ?? DEFAULT_TWIN_WINDOW_YEARS,
      top_k: params.topK ?? 5,
    },
  });
  return data;
}

export async function searchRegions(query: string): Promise<RegionNameInfo[]> {
  if (query.trim().length < 2) return [];
  // 법정동(리) grain 응답 — 시군구·읍면동 단위 옵션은 호출부에서 sigungu_code/eupmyeondong_code로 dedup.
  // 큰 시군구(예: 흥덕구)의 모든 읍면동이 걸리도록 여유 있게 조회.
  const { data } = await apiClient.get<RegionNameInfo[]>("/free/v2/regions", {
    params: { search: query.trim(), limit: 200 },
  });
  return data;
}

export async function resolveRegionName(params: {
  regionLevel: RegionLevel;
  regionCode: string;
}): Promise<RegionNameInfo | null> {
  const query: Record<string, string | number> = { limit: 1 };
  if (params.regionLevel === "eupmyeondong") {
    query.eupmyeondong_code = params.regionCode;
  } else if (params.regionLevel === "sigungu") {
    query.sigungu_code = params.regionCode;
  } else {
    // sido/city — 정적 매핑으로 처리(utils/sido.ts), API 호출 생략
    return null;
  }
  const { data } = await apiClient.get<RegionNameInfo[]>("/free/v2/regions", {
    params: query,
  });
  return data[0] ?? null;
}
