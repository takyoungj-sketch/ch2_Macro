import type { RegionItem, RegionLevel } from "../types";
import type { TierCodes } from "./regionTier";

export type LongTermRegionLevel = RegionLevel | "beopjungri";

export interface LongTermRegionTarget {
  region_level: LongTermRegionLevel;
  region_code: string;
}

const MAX = 10;

/**
 * 장기 추세 API용 (level, code) 목록.
 * 상위 행정만 선택 시 해당 레벨 1선 — 법정동·리로 펼치지 않음.
 */
export function resolveLongTermTargets(tier: TierCodes): LongTermRegionTarget[] {
  const beops = tier.beopjungri_codes.map((c) => c.trim()).filter(Boolean);
  if (beops.length > 0) {
    return beops.slice(0, MAX).map((c) => ({ region_level: "beopjungri", region_code: c }));
  }
  const eups = tier.eupmyeondong_codes.map((c) => c.trim()).filter(Boolean);
  if (eups.length > 0) {
    return eups.slice(0, MAX).map((c) => ({ region_level: "eupmyeondong", region_code: c }));
  }
  const sgs = tier.sigungu_codes.map((c) => c.trim()).filter(Boolean);
  if (sgs.length > 0) {
    return sgs.slice(0, MAX).map((c) => ({ region_level: "sigungu", region_code: c }));
  }
  const cities = tier.city_codes.map((c) => c.trim()).filter(Boolean);
  if (cities.length > 0) {
    return cities.slice(0, MAX).map((c) => ({ region_level: "city", region_code: c }));
  }
  const sidos = tier.sido_codes.map((c) => c.trim()).filter(Boolean);
  if (sidos.length > 0) {
    return sidos.slice(0, MAX).map((c) => ({ region_level: "sido", region_code: c }));
  }
  return [];
}

/** tier 에 명시 선택이 없을 때 filterRequest.region_codes fallback (법정동·리). */
export function longTermTargetsFromBeopjungriCodes(codes: string[]): LongTermRegionTarget[] {
  return [...new Set(codes.map((c) => c.trim()).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b, "ko-KR"))
    .slice(0, MAX)
    .map((c) => ({ region_level: "beopjungri", region_code: c }));
}

export function resolveLongTermTargetsForFetch(
  tier: TierCodes,
  fallbackBeopjungriCodes: string[],
): LongTermRegionTarget[] {
  const explicit = resolveLongTermTargets(tier);
  if (explicit.length > 0) return explicit;
  return longTermTargetsFromBeopjungriCodes(fallbackBeopjungriCodes);
}

export function longTermTargetLabel(
  regions: readonly RegionItem[],
  target: LongTermRegionTarget,
): string {
  const c = target.region_code.trim();
  if (target.region_level === "beopjungri") {
    const row = regions.find((r) => String(r.beopjungri_code).trim() === c);
    return row?.beopjungri_name?.trim() || c;
  }
  if (target.region_level === "eupmyeondong") {
    const row = regions.find((r) => String(r.eupmyeondong_code).trim() === c);
    return row?.eupmyeondong_name?.trim() || c;
  }
  if (target.region_level === "sigungu") {
    const row = regions.find((r) => String(r.sigungu_code).trim() === c);
    return row?.sigungu_name?.trim() || c;
  }
  if (target.region_level === "sido") {
    const row = regions.find((r) => String(r.sido_code).trim() === c);
    return row?.sido_name?.trim() || c;
  }
  if (target.region_level === "city") {
    const row = regions.find((r) => {
      const sg = String(r.sigungu_code ?? "").trim();
      if (sg.length !== 5) return false;
      const bucket = String(Math.floor(Number(sg) / 10) * 10).padStart(5, "0");
      return bucket === c;
    });
    if (row?.sigungu_name) {
      const parts = row.sigungu_name.split(/\s+/);
      if (parts[0]?.endsWith("시")) return parts[0];
    }
    return c;
  }
  return c;
}
