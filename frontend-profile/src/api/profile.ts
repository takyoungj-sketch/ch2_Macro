import { isAxiosError } from "axios";
import { cityBucketFromSigungu } from "@ch2/region-picker";
import { apiClient } from "./client";
import type {
  ProfileTwinNeighborsResponse,
  RegionLevel,
  RegionNameInfo,
  RegionalProfileResponse,
} from "../types";

/** D-029 Phase A. 재빌드 전엔 v2.0으로 fallback. */
export const DEFAULT_PROFILE_VERSION = "v2.1-national";
export const FALLBACK_PROFILE_VERSION = "v2.0-national";
export const DEFAULT_WINDOW_YEARS = 3;

// Profile-native Twin v2.1 (D-029 Phase B). legacy hybrid fallback은 API에서 v6/v7.
export const DEFAULT_TWIN_PROFILE_VERSION = "v2.1-national";
export const LEGACY_TWIN_PROFILE_VERSION = "v1.1-national";
export const DEFAULT_TWIN_WINDOW_YEARS = 3;

async function getRegionalProfile(
  regionLevel: RegionLevel,
  regionCode: string,
  profileVersion: string,
  windowYears: number,
): Promise<RegionalProfileResponse> {
  const { data } = await apiClient.get<RegionalProfileResponse>("/regional-profile", {
    params: {
      region_level: regionLevel,
      region_code: regionCode,
      profile_version: profileVersion,
      window_years: windowYears,
    },
  });
  return data;
}

export async function fetchRegionalProfile(params: {
  regionLevel: RegionLevel;
  regionCode: string;
  profileVersion?: string;
  windowYears?: number;
}): Promise<RegionalProfileResponse> {
  const windowYears = params.windowYears ?? DEFAULT_WINDOW_YEARS;
  const preferred = params.profileVersion ?? DEFAULT_PROFILE_VERSION;
  try {
    return await getRegionalProfile(params.regionLevel, params.regionCode, preferred, windowYears);
  } catch (err) {
    if (
      !params.profileVersion &&
      preferred === DEFAULT_PROFILE_VERSION &&
      isAxiosError(err) &&
      err.response?.status === 404
    ) {
      return getRegionalProfile(
        params.regionLevel,
        params.regionCode,
        FALLBACK_PROFILE_VERSION,
        windowYears,
      );
    }
    throw err;
  }
}

export async function fetchTwinNeighbors(params: {
  regionLevel: RegionLevel;
  regionCode: string;
  profileVersion?: string;
  windowYears?: number;
  topK?: number;
}): Promise<ProfileTwinNeighborsResponse> {
  let path: string;
  if (params.regionLevel === "sigungu") {
    path = `/regional-profile/twins-sigungu/${params.regionCode}`;
  } else if (params.regionLevel === "beopjungri") {
    path = `/regional-profile/twins-beop/${params.regionCode}`;
  } else {
    path = `/regional-profile/twins/${params.regionCode.trim().slice(0, 8)}`;
  }
  const { data } = await apiClient.get<ProfileTwinNeighborsResponse>(path, {
    params: {
      profile_version: params.profileVersion ?? DEFAULT_TWIN_PROFILE_VERSION,
      window_years: params.windowYears ?? DEFAULT_TWIN_WINDOW_YEARS,
      top_k: params.topK ?? 5,
    },
  });
  return data;
}

/** 전체 카탈로그 — loose 주소·Enter 확정 resolver용 (토지 RegionSelector와 동일). */
export async function fetchRegions(params?: {
  search?: string;
  limit?: number;
}): Promise<RegionNameInfo[]> {
  const p: Record<string, string | number> = params ? { ...params } : {};
  const hasSearch = Boolean(params?.search && params.search.trim().length > 0);
  if (!hasSearch && p.limit === undefined) {
    p.limit = 50000;
  }
  const { data } = await apiClient.get<RegionNameInfo[]>("/free/v2/regions", {
    params: p,
  });
  return data;
}

export async function searchRegions(query: string): Promise<RegionNameInfo[]> {
  if (query.trim().length < 2) return [];
  // 법정동(리) grain 응답 — 시군구·읍면동 단위 옵션은 호출부에서 sigungu_code/eupmyeondong_code로 dedup.
  // 큰 시군구(예: 흥덕구)의 모든 읍면동이 걸리도록 여유 있게 조회.
  return fetchRegions({ search: query.trim(), limit: 400 });
}

export async function resolveRegionName(params: {
  regionLevel: RegionLevel;
  regionCode: string;
}): Promise<RegionNameInfo | null> {
  const code = params.regionCode.trim();
  const query: Record<string, string | number> = { limit: 1 };
  if (params.regionLevel === "beopjungri") {
    query.beopjungri_code = code;
  } else if (params.regionLevel === "eupmyeondong") {
    query.eupmyeondong_code = code;
  } else if (params.regionLevel === "sigungu") {
    query.sigungu_code = code;
  } else if (params.regionLevel === "city") {
    const base = parseInt(code, 10);
    if (Number.isNaN(base)) return null;
    for (let off = 1; off <= 9; off++) {
      const sgCode = String(base + off).padStart(5, "0");
      const { data } = await apiClient.get<RegionNameInfo[]>("/free/v2/regions", {
        params: { sigungu_code: sgCode, limit: 1 },
      });
      const row = data[0];
      if (row && cityBucketFromSigungu(row.sigungu_code) === code) return row;
    }
    // fallback: 전국 카탈로그에서 bucket 매칭 (sigungu probe 실패 시)
    const rows = await fetchRegions();
    return rows.find((r) => cityBucketFromSigungu(r.sigungu_code) === code) ?? null;
  } else {
    // sido — 정적 매핑으로 처리(utils/sido.ts), API 호출 생략
    return null;
  }
  const { data } = await apiClient.get<RegionNameInfo[]>("/free/v2/regions", {
    params: query,
  });
  return data[0] ?? null;
}
