import type { RegionItem } from "../types";

/** 지역 선택 — 각 차원별 코드(복수). 빈 차원은 그 조건 무시. AND 조합. */
export interface TierCodes {
  sido_codes: string[];
  sigungu_codes: string[];
  eupmyeondong_codes: string[];
  beopjungri_codes: string[];
}

export const emptyTierCodes = (): TierCodes => ({
  sido_codes: [],
  sigungu_codes: [],
  eupmyeondong_codes: [],
  beopjungri_codes: [],
});

/** 상위 선택이 비어 있으면 해당 차원에서 필터를 걸지 않는다. */
export function resolveBeopjungriCodes(
  regions: RegionItem[],
  tier: TierCodes
): string[] {
  let cand = [...regions];

  if (tier.sido_codes.length > 0) {
    const set = new Set(tier.sido_codes.map((c) => c.trim()));
    cand = cand.filter((r) => set.has(String(r.sido_code).trim()));
  }
  if (tier.sigungu_codes.length > 0) {
    const set = new Set(tier.sigungu_codes.map((c) => c.trim()));
    cand = cand.filter((r) => set.has(String(r.sigungu_code).trim()));
  }
  if (tier.eupmyeondong_codes.length > 0) {
    const set = new Set(tier.eupmyeondong_codes.map((c) => c.trim()));
    cand = cand.filter((r) => set.has(String(r.eupmyeondong_code).trim()));
  }
  if (tier.beopjungri_codes.length > 0) {
    const set = new Set(tier.beopjungri_codes.map((c) => c.trim()));
    cand = cand.filter((r) => set.has(String(r.beopjungri_code).trim()));
  }

  const out = [...new Set(cand.map((r) => String(r.beopjungri_code).trim()))];
  out.sort((a, b) => a.localeCompare(b));
  return out;
}

/** `by_region` 등 법정리 코드 → 표시용 명칭 (로드된 regions 목록 기준) */
export function beopjungriNameForCode(
  regions: RegionItem[],
  beopjungriCode: string
): string {
  const c = String(beopjungriCode).trim();
  const row = regions.find((r) => String(r.beopjungri_code).trim() === c);
  const name = row?.beopjungri_name?.trim();
  return name && name.length > 0 ? name : c;
}
