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
 * Profile 조회용 region 해석.
 * 상위 행정 단독 선택이면 그대로, 법정동·리만 있으면 동일 읍면동(코드 앞 8자리)으로 승격.
 */
export function resolveProfileRegionFromTier(
  tierSelection: TierCodes
): { level: RegionLevel; code: string; escalatedFromBeop: boolean } | null {
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
  if (beops.length === 0) return null;

  const eupCodes = new Set(beops.map((b) => (b.length >= 8 ? b.slice(0, 8) : b.padEnd(8, "0").slice(0, 8))));
  if (eupCodes.size !== 1) return null;

  const eup = [...eupCodes][0]!;
  if (!/^\d{8}$/.test(eup)) return null;

  return { level: "eupmyeondong", code: eup, escalatedFromBeop: true };
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
    window_years: up.window_years as 3 | 5,
    total: up.total,
    by_year: up.by_year,
    by_zone: up.by_zone,
    by_land_category: up.by_land_category,
    matrix: up.matrix,
    stats_excluded_codes: [],
    analysis_base_key: null,
    by_year_calendar_reference: up.by_year_calendar_reference,
  };
}
