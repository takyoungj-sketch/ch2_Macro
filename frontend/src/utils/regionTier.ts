import type { RegionItem } from "../types";
import { cityBucketFromSigungu } from "./cityBucket";

/** 지역 선택 — 각 차원별 코드(복수). 빈 차원은 그 조건 무시. AND 조합. */
export interface TierCodes {
  sido_codes: string[];
  sigungu_codes: string[];
  /** 자치구로 나뉜 시 등: 5자리 버킷 코드(예: 청주 43110). cityBucketFromSigungu 와 동일 규칙. */
  city_codes: string[];
  eupmyeondong_codes: string[];
  beopjungri_codes: string[];
}

export const emptyTierCodes = (): TierCodes => ({
  sido_codes: [],
  sigungu_codes: [],
  city_codes: [],
  eupmyeondong_codes: [],
  beopjungri_codes: [],
});

/** 상위 선택이 비어 있으면 해당 차원에서 필터를 걸지 않는다. */
export function resolveBeopjungriCodes(
  regions: readonly RegionItem[],
  tier: TierCodes
): string[] {
  let cand = [...regions];

  if (tier.sido_codes.length > 0) {
    const set = new Set(tier.sido_codes.map((c) => c.trim()));
    cand = cand.filter((r) => set.has(String(r.sido_code).trim()));
  }
  if (tier.city_codes.length > 0) {
    const buckets = new Set(tier.city_codes.map((c) => c.trim()));
    cand = cand.filter((r) => {
      const b = cityBucketFromSigungu(String(r.sigungu_code ?? ""));
      return b && buckets.has(b);
    });
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
  out.sort((a, b) => a.localeCompare(b, "ko-KR"));
  return out;
}

/**
 * 검색·시군구·읍면 칩 선택용: 차원별로 지정된 법정코드 명시 목록 ∪ 상위 행정구역에 속하는 모든 법정코드를 합합니다.
 */
export function resolveUnionBeopjungriCodes(regions: readonly RegionItem[], tier: TierCodes): string[] {
  const out = new Set<string>();
  const add = (c: string | null | undefined) => {
    const t = String(c ?? "").trim();
    if (t) out.add(t);
  };

  if (tier.sido_codes.length > 0) {
    const sd = new Set(tier.sido_codes.map((x) => x.trim()));
    for (const r of regions) {
      if (sd.has(String(r.sido_code ?? "").trim())) add(r.beopjungri_code);
    }
  }

  if (tier.city_codes.length > 0) {
    const buckets = new Set(tier.city_codes.map((x) => x.trim()));
    for (const r of regions) {
      const b = cityBucketFromSigungu(String(r.sigungu_code ?? ""));
      if (b && buckets.has(b)) add(r.beopjungri_code);
    }
  }

  if (tier.sigungu_codes.length > 0) {
    const sg = new Set(tier.sigungu_codes.map((x) => x.trim()));
    for (const r of regions) {
      if (sg.has(String(r.sigungu_code ?? "").trim())) add(r.beopjungri_code);
    }
  }

  if (tier.eupmyeondong_codes.length > 0) {
    const eu = new Set(tier.eupmyeondong_codes.map((x) => x.trim()));
    for (const r of regions) {
      if (eu.has(String(r.eupmyeondong_code ?? "").trim())) add(r.beopjungri_code);
    }
  }

  for (const c of tier.beopjungri_codes) {
    add(c);
  }

  const list = [...out].filter(Boolean);
  list.sort((a, b) => a.localeCompare(b, "ko-KR"));
  return list;
}

/** `by_region` 등 법정리 코드 → 표시용 명칭 (로드된 regions 목록 기준) */
export function beopjungriNameForCode(
  regions: readonly RegionItem[],
  beopjungriCode: string
): string {
  const c = String(beopjungriCode).trim();
  const row = regions.find((r) => String(r.beopjungri_code).trim() === c);
  const name = row?.beopjungri_name?.trim();
  return name && name.length > 0 ? name : c;
}
