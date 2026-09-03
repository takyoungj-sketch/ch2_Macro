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
  /** 리가 없는 동을 읍면동으로 올렸을 때의 원래 10자리 (프로필 전용, D-057). */
  originBeopCode?: string;
}
