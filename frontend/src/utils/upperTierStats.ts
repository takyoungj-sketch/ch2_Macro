import type { FreeStatsV2Response, RegionItem, RegionLevel, UpperStatsV2Response } from "../types";
import type { TierCodes } from "./regionTier";
import { isLegalDongWithoutRi } from "@ch2/region-picker";

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
 * Profile 조회용 region 해석 (D-030 P1-a, D-057).
 * 상위 행정 단독 선택이면 그대로. 실제 리(10자리, …00 아님)는 beopjungri.
 * 리가 없는 법정동(…00)만 읍면동 8자리로 연다 — 토지 칩은 바꾸지 않는다.
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

  if (isLegalDongWithoutRi(beop)) {
    return { level: "eupmyeondong", code: beop.slice(0, 8), escalatedFromBeop: true };
  }

  return { level: "beopjungri", code: beop, escalatedFromBeop: false };
}

function onlyCode(codes: readonly string[]): string {
  const cleaned = codes.map((code) => code.trim()).filter(Boolean);
  return cleaned.length === 1 ? cleaned[0]! : "";
}

/** AI2에 넘길 화면 지역 이름. 같은 단계에서 둘 이상이면 빈 문자열. */
export function landScreenRegion(tier: TierCodes, regions: readonly RegionItem[]): string {
  const beop = onlyCode(tier.beopjungri_codes);
  if (tier.beopjungri_codes.map((code) => code.trim()).filter(Boolean).length > 1) return "";
  if (beop) return regions.find((row) => row.beopjungri_code === beop)?.beopjungri_name ?? "";
  const eup = onlyCode(tier.eupmyeondong_codes);
  if (tier.eupmyeondong_codes.map((code) => code.trim()).filter(Boolean).length > 1) return "";
  if (eup) return regions.find((row) => row.eupmyeondong_code === eup)?.eupmyeondong_name ?? "";
  const sigungu = onlyCode(tier.sigungu_codes);
  if (tier.sigungu_codes.map((code) => code.trim()).filter(Boolean).length > 1) return "";
  if (sigungu) return regions.find((row) => row.sigungu_code === sigungu)?.sigungu_name ?? "";
  const sido = onlyCode(tier.sido_codes);
  if (tier.city_codes.map((code) => code.trim()).filter(Boolean).length > 0) return "";
  if (sido) return regions.find((row) => row.sido_code === sido)?.sido_name ?? "";
  return "";
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
