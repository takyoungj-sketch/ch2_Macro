import { isSejongRegionRow } from "./sejongRegion";
import type { RegionNameInfo } from "./types";

/** 자동완성·칩에 쓸 전체 명칭(동명 구분용 상위 포함) */
export function formatRegionHierarchyLabel(r: RegionNameInfo): string {
  const raw = isSejongRegionRow(r)
    ? [r.sido_name, r.sigungu_name, r.beopjungri_name]
    : [r.sido_name, r.sigungu_name, r.eupmyeondong_name, r.beopjungri_name];
  const mapped = raw.map((s) => String(s ?? "").trim());
  const seen = new Set<string>();
  const parts: string[] = [];
  for (const x of mapped) {
    if (!x) continue;
    const k = x.toLowerCase();
    if (seen.has(k)) continue;
    seen.add(k);
    parts.push(x);
  }
  return parts.join(" ") || String(r.beopjungri_code).trim();
}
