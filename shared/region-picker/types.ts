export type RegionLevel = "sido" | "sigungu" | "eupmyeondong" | "beopjungri" | "city";

export interface RegionNameInfo {
  sido_code: string;
  sido_name: string;
  sigungu_code: string;
  sigungu_name: string;
  eupmyeondong_code: string;
  eupmyeondong_name: string;
  beopjungri_code: string;
  beopjungri_name: string;
}

export interface RegionSearchResult {
  level: RegionLevel;
  code: string;
  label: string;
  sublabel: string;
}
