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

/** 읍·면·동 행정 칩 + 법정동·리 줄 개수 합계(각각 시군구 미만 선택 1단위로 셈). */
export function paidSubSigunguSelectionsCount(tier: TierCodes): number {
  const eup = tier.eupmyeondong_codes.map((c) => c.trim()).filter(Boolean).length;
  const bp = tier.beopjungri_codes.map((c) => c.trim()).filter(Boolean).length;
  return eup + bp;
}

/** 유료 패널: 시도·군구 위 선택 없음일 때 사용자가 고른 순서를 보여 줄 시군구 미만 선택 한 줄 단위 */
export type PaidSubSigunguPickEntry =
  | { kind: "eup"; code: string }
  | { kind: "beop"; code: string };

/**
 * `preferredSeq` 순서를 유지하며 tier 에 없는 항목만 제거·중복 제거 후,
 * tier 에만 있는 읍면·법정은 각각 코드 순으로 뒤에 붙입니다.
 */
export function reconcilePaidSubSigunguPickOrder(
  preferredSeq: readonly PaidSubSigunguPickEntry[],
  tier: TierCodes
): PaidSubSigunguPickEntry[] {
  const eupInTier = [...new Set(tier.eupmyeondong_codes.map((c) => String(c ?? "").trim()).filter(Boolean))].sort(
    (a, b) => a.localeCompare(b, "ko-KR")
  );
  const beopInTier = [...new Set(tier.beopjungri_codes.map((c) => String(c ?? "").trim()).filter(Boolean))].sort(
    (a, b) => a.localeCompare(b, "ko-KR")
  );
  const eupSet = new Set(eupInTier);
  const beopSet = new Set(beopInTier);

  const out: PaidSubSigunguPickEntry[] = [];
  const placed = new Set<string>();

  const tryPlace = (e: PaidSubSigunguPickEntry): void => {
    const c = String(e.code ?? "").trim();
    if (!c) return;
    const k = `${e.kind}:${c}`;
    if (placed.has(k)) return;
    if (e.kind === "eup" && eupSet.has(c)) {
      out.push({ kind: "eup", code: c });
      placed.add(k);
    }
    if (e.kind === "beop" && beopSet.has(c)) {
      out.push({ kind: "beop", code: c });
      placed.add(k);
    }
  };

  for (const e of preferredSeq) tryPlace(e);
  for (const c of eupInTier) tryPlace({ kind: "eup", code: c });
  for (const c of beopInTier) tryPlace({ kind: "beop", code: c });
  return out;
}

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
