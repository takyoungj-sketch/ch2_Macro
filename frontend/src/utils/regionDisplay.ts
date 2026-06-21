import type { RegionItem, RegionLevel } from "../types";
import { cityBucketFromSigungu } from "./cityBucket";
import { isSejongPseudoSigunguCode } from "./sejongRegion";

/** 자동완성·칩에 쓸 전체 명칭(동명 구분용 상위 포함) */
export function formatRegionHierarchyLabel(r: RegionItem): string {
  const raw = [
    r.sido_name,
    r.sigungu_name,
    r.eupmyeondong_name,
    r.beopjungri_name,
  ].map((s) => String(s ?? "").trim());
  const seen = new Set<string>();
  const parts: string[] = [];
  for (const x of raw) {
    if (!x) continue;
    const k = x.toLowerCase();
    if (seen.has(k)) continue;
    seen.add(k);
    parts.push(x);
  }
  return parts.join(" ") || String(r.beopjungri_code).trim();
}

export const PROFILE_REGION_LEVEL_LABEL: Record<RegionLevel, string> = {
  sido: "시·도",
  city: "시(자치구 묶음)",
  sigungu: "시군구",
  eupmyeondong: "읍·면·동",
};

/** Profile 조회 대상의 한글 지역명 (regions 카탈로그 기준) */
export function resolveProfileRegionLabel(
  regions: readonly RegionItem[],
  target: { level: RegionLevel; code: string }
): string {
  const code = String(target.code ?? "").trim();
  if (!code) return code;

  switch (target.level) {
    case "sido": {
      const row = regions.find((r) => String(r.sido_code ?? "").trim() === code);
      return row?.sido_name ? String(row.sido_name).trim() : code;
    }
    case "sigungu": {
      if (isSejongPseudoSigunguCode(code)) {
        const row = regions.find((r) =>
          isSejongPseudoSigunguCode(String(r.sigungu_code ?? "").trim())
        );
        const sido = row?.sido_name ? String(row.sido_name).trim() : "세종특별자치시";
        return `${sido} 전체`;
      }
      const row = regions.find((r) => String(r.sigungu_code ?? "").trim() === code);
      if (!row) return code;
      return [row.sido_name, row.sigungu_name]
        .map((x) => String(x ?? "").trim())
        .filter(Boolean)
        .join(" ");
    }
    case "eupmyeondong": {
      const row = regions.find((r) => String(r.eupmyeondong_code ?? "").trim() === code);
      if (!row) return code;
      return [row.sido_name, row.sigungu_name, row.eupmyeondong_name]
        .map((x) => String(x ?? "").trim())
        .filter(Boolean)
        .join(" ");
    }
    case "city": {
      const row = regions.find(
        (r) => cityBucketFromSigungu(String(r.sigungu_code ?? "")) === code
      );
      if (!row) return code;
      const toks = String(row.sigungu_name ?? "")
        .trim()
        .split(/\s+/)
        .filter(Boolean);
      const head = toks[0] ?? "";
      const cityTok = /시$/.test(head) ? head : head || code;
      return [row.sido_name, cityTok].map((x) => String(x ?? "").trim()).filter(Boolean).join(" ");
    }
    default:
      return code;
  }
}
