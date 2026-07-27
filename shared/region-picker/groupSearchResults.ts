import { cityBucketFromSigungu, extractCityFirstToken } from "./cityBucket";
import type { RegionNameInfo, RegionSearchResult } from "./types";

/** `/free/v2/regions` hit → Profile 검색 제안 (토지 tier dedup과 동일 grain). */
export function groupProfileSearchResults(rows: RegionNameInfo[]): {
  sido: RegionSearchResult[];
  city: RegionSearchResult[];
  sigungu: RegionSearchResult[];
  eup: RegionSearchResult[];
  beop: RegionSearchResult[];
} {
  const sidoMap = new Map<string, RegionSearchResult>();
  const cityMap = new Map<string, RegionSearchResult>();
  const sigunguMap = new Map<string, RegionSearchResult>();
  const eupMap = new Map<string, RegionSearchResult>();
  const beopMap = new Map<string, RegionSearchResult>();

  for (const r of rows) {
    if (r.sido_code && !sidoMap.has(r.sido_code)) {
      sidoMap.set(r.sido_code, {
        level: "sido",
        code: r.sido_code,
        label: `${r.sido_name} 전체`,
        sublabel: "시/도",
      });
    }
    if (r.sigungu_code) {
      const cityCode = cityBucketFromSigungu(r.sigungu_code);
      const cityTok = extractCityFirstToken(r.sigungu_name);
      if (cityTok && cityCode && !cityMap.has(cityCode)) {
        cityMap.set(cityCode, {
          level: "city",
          code: cityCode,
          label: `${cityTok} 전체`,
          sublabel: r.sido_name,
        });
      }
    }
    if (r.sigungu_code && !sigunguMap.has(r.sigungu_code)) {
      sigunguMap.set(r.sigungu_code, {
        level: "sigungu",
        code: r.sigungu_code,
        label: `${r.sigungu_name} 전체`,
        sublabel: r.sido_name,
      });
    }
    if (r.eupmyeondong_code && !eupMap.has(r.eupmyeondong_code)) {
      eupMap.set(r.eupmyeondong_code, {
        level: "eupmyeondong",
        code: r.eupmyeondong_code,
        label: r.eupmyeondong_name,
        sublabel: `${r.sido_name} ${r.sigungu_name}`,
      });
    }
    if (r.beopjungri_code && !beopMap.has(r.beopjungri_code)) {
      const isDongOnly = r.beopjungri_code.endsWith("00") && r.beopjungri_name === r.eupmyeondong_name;
      if (!isDongOnly) {
        beopMap.set(r.beopjungri_code, {
          level: "beopjungri",
          code: r.beopjungri_code,
          label: r.beopjungri_name,
          sublabel: `${r.sido_name} ${r.sigungu_name} ${r.eupmyeondong_name}`,
        });
      }
    }
  }

  return {
    sido: [...sidoMap.values()],
    city: [...cityMap.values()],
    sigungu: [...sigunguMap.values()],
    eup: [...eupMap.values()],
    beop: [...beopMap.values()],
  };
}
