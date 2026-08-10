import type { FreeStatsV2Response, RegionLevel, UpperStatsV2Response } from "../types";
import type { TierCodes } from "./regionTier";

/**
 * 단일 상위 행정구역(시·도/시군구/읍면동/의사 시) 단독 선택 여부 — DECISIONS D-009/D-010.
 * 법정동·리 선택이 하나라도 있으면 null.
 */
export function resolveUpperSingleFromTier(
  tierSelection: TierCodes
): { level: RegionLevel; code: string } | null {
  const sidoN = tierSelection.sido_codes.length;
  const cityN = tierSelection.city_codes.length;
  const sigunguN = tierSelection.sigungu_codes.length;
  const eupN = tierSelection.eupmyeondong_codes.length;
  const beopN = tierSelection.beopjungri_codes.length;
  if (beopN > 0) return null;
  if (cityN === 1 && sidoN === 0 && sigunguN === 0 && eupN === 0) {
    return { level: "city", code: tierSelection.city_codes[0]! };
  }
  if (sidoN === 1 && sigunguN === 0 && eupN === 0 && cityN === 0) {
    return { level: "sido", code: tierSelection.sido_codes[0]! };
  }
  if (sidoN === 0 && sigunguN === 1 && eupN === 0 && cityN === 0) {
    return { level: "sigungu", code: tierSelection.sigungu_codes[0]! };
  }
  if (sidoN === 0 && sigunguN === 0 && eupN === 1 && cityN === 0) {
    return { level: "eupmyeondong", code: tierSelection.eupmyeondong_codes[0]! };
  }
  return null;
}

/**
 * Profile 조회용 region 해석 (D-030 P1-a).
 * 상위 행정 단독 선택이면 그대로. 법정리만 있으면 단일 beop → beopjungri grain (eup 승격 폐지).
 */
export type ProfileRegionLevel = RegionLevel | "beopjungri";

export function resolveProfileRegionFromTier(
  tierSelection: TierCodes
): { level: ProfileRegionLevel; code: string; escalatedFromBeop: boolean } | null {
  const direct = resolveUpperSingleFromTier(tierSelection);
  if (direct) {
    return { ...direct, escalatedFromBeop: false };
  }

  const hasUpperChip =
    tierSelection.sido_codes.length > 0 ||
    tierSelection.city_codes.length > 0 ||
    tierSelection.sigungu_codes.length > 0 ||
    tierSelection.eupmyeondong_codes.length > 0;
  if (hasUpperChip) return null;

  const beops = tierSelection.beopjungri_codes.map((b) => b.trim()).filter(Boolean);
  if (beops.length !== 1) return null;

  const beop = beops[0]!;
  if (!/^\d{10}$/.test(beop)) return null;

  return { level: "beopjungri", code: beop, escalatedFromBeop: false };
}

/** `/paid/upper-stats/…` 응답을 FreeStatsV2Response 로 맞춤 — 기본통계 카드 재사용. */
export function upperToFreeStatsShape(up: UpperStatsV2Response): FreeStatsV2Response {
  return {
    beopjungri_code: up.region_code,
    beopjungri_name: up.region_name,
    as_of_month: up.as_of_month,
    stats_reference_date: up.stats_reference_date,
    period_start: up.period_start,
    period_end: up.period_end,
    window_years: up.window_years as 3 | 5 | 7,
    total: up.total,
    by_year: up.by_year,
    by_zone: up.by_zone,
    by_land_category: up.by_land_category,
    matrix: up.matrix,
    matrix_mode: up.matrix_mode,
    stats_excluded_codes: [],
    analysis_base_key: null,
    by_year_calendar_reference: up.by_year_calendar_reference,
  };
}
