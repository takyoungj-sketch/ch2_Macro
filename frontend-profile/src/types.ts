// backend/app/regional_profile/router.py 응답 스키마와 동일 (D-027 §12)

export type RegionLevel = "sido" | "sigungu" | "eupmyeondong" | "beopjungri" | "city";

export interface RegionalProfileMeta {
  profile_version: string;
  as_of_month: string;
  window_years: number;
  region_level: RegionLevel;
  region_code: string;
  feature_count?: number | null;
  builder_version?: string | null;
  validation_status: string;
  computed_at?: string | null;
}

export interface YearlyTypeCell {
  count: number;
  amount: number; // 만원
}

/** 8대 시장유형: 토지/상가/공장/단독다가구/아파트/오피스텔/연립다세대/분양권 */
export const YEARLY_MIX_TYPES = [
  "토지",
  "상가",
  "공장",
  "단독다가구",
  "아파트",
  "오피스텔",
  "연립다세대",
  "분양권",
] as const;
export type YearlyMixType = (typeof YEARLY_MIX_TYPES)[number];

export interface YearlyMix {
  years: number[];
  totals_by_type: Record<YearlyMixType, YearlyTypeCell>;
  total_count_3y: number;
  total_amount_3y: number;
  dominant_type: YearlyMixType;
  count_share_by_type: Record<YearlyMixType, number>;
  amount_share_by_type: Record<YearlyMixType, number>;
  // "2023" | "2024" | "2025" ... → 8유형 count/amount (동적 연도 키)
  [year: string]: unknown;
}

export interface JimokGroupTop3Item {
  group: string;
  label: string;
  count: number;
  share: number;
}

/** D-029: 용도×지목군 Top1~3 (JSONB flat + object) */
export interface LandTopItem {
  zone: string;
  jimok: string;
  jimok_code: string;
  count: number;
  mean_manwon_per_sqm?: number | null;
}

export interface RegionalProfileFeatures {
  population?: number;
  yearly_mix?: YearlyMix;
  dominant_type?: YearlyMixType;
  market_presence?: Record<string, number>;
  jimok_group_top3?: JimokGroupTop3Item[];
  jimok_group_composition?: Record<string, number>;
  jimok_group_total_count?: number;
  land_top1?: LandTopItem;
  land_top2?: LandTopItem;
  land_top3?: LandTopItem;
  land_top1_zone?: string;
  land_top1_jimok?: string;
  land_top1_jimok_code?: string;
  land_top1_count?: number;
  land_top1_mean_manwon_per_sqm?: number;
  apartment_count?: number;
  apartment_mean?: number;
  apartment_median?: number;
  apartment_p25?: number;
  apartment_p75?: number;
  [key: string]: unknown;
}

export interface RegionalProfileResponse {
  meta: RegionalProfileMeta;
  features: RegionalProfileFeatures;
}

export interface TwinDetailScores {
  [key: string]: unknown;
}

export interface ProfileTwinNeighborItem {
  rank: number;
  twin_eupmyeondong_code?: string;
  twin_eupmyeondong_name?: string;
  twin_beopjungri_code?: string;
  twin_beopjungri_name?: string;
  twin_sigungu_code?: string;
  twin_sigungu_name: string;
  twin_sido_name: string;
  similarity_score: number;
  detail_scores: TwinDetailScores;
}

export interface ProfileTwinNeighborsResponse {
  profile_version: string;
  window_years: number;
  algorithm_version?: number;
  scope?: string | null;
  anchor_eupmyeondong_code?: string;
  anchor_beopjungri_code?: string;
  anchor_sigungu_code?: string;
  neighbors: ProfileTwinNeighborItem[];
}

export interface RegionNameInfo {
  beopjungri_code: string;
  beopjungri_name: string;
  eupmyeondong_code: string;
  eupmyeondong_name: string;
  sigungu_code: string;
  sigungu_name: string;
  sido_code: string;
  sido_name: string;
}
