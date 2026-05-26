import type { RegionItem, TwinEupAnchor, TwinSigunguAnchor } from "../types";

/**
 * 확정된 법정동 코드 목록이 모두 동일 시군구에 속할 때만 앵커 시군구를 반환한다.
 * (시·도 전체 등 복수 시군구가 섞이면 null)
 */
export function resolveTwinAnchorSigungu(
  regions: RegionItem[],
  resolvedBeopjungriCodes: string[],
): TwinSigunguAnchor | null {
  const wants = new Set(resolvedBeopjungriCodes.map((c) => c.trim()).filter(Boolean));
  if (wants.size === 0) return null;

  const matches = regions.filter((r) => wants.has(r.beopjungri_code.trim()));
  const matchedBeop = new Set(matches.map((m) => m.beopjungri_code.trim()));
  for (const c of wants) {
    if (!matchedBeop.has(c)) return null;
  }

  const bySigungu = new Map<string, RegionItem>();
  for (const r of matches) {
    bySigungu.set(r.sigungu_code.trim(), r);
  }
  if (bySigungu.size !== 1) return null;

  const row = [...bySigungu.values()][0]!;
  return {
    sigungu_code: row.sigungu_code.trim(),
    sido_code: row.sido_code.trim(),
    sigungu_name: row.sigungu_name,
    sido_name: row.sido_name,
  };
}

/**
 * 확정 법정동·리 목록이 모두 동일 읍면동(표준 코드 8자리)에 속할 때만 앵커를 반환한다.
 */
export function resolveTwinAnchorEupmyeondong(
  regions: RegionItem[],
  resolvedBeopjungriCodes: string[],
): TwinEupAnchor | null {
  const wants = new Set(resolvedBeopjungriCodes.map((c) => c.trim()).filter(Boolean));
  if (wants.size === 0) return null;

  const matches = regions.filter((r) => wants.has(r.beopjungri_code.trim()));
  const matchedBeop = new Set(matches.map((m) => m.beopjungri_code.trim()));
  for (const c of wants) {
    if (!matchedBeop.has(c)) return null;
  }

  const byEup = new Map<string, RegionItem>();
  for (const r of matches) {
    const eup = r.eupmyeondong_code.trim();
    byEup.set(eup, r);
  }
  if (byEup.size !== 1) return null;

  const row = [...byEup.values()][0]!;
  return {
    eupmyeondong_code: row.eupmyeondong_code.trim(),
    eupmyeondong_name: row.eupmyeondong_name,
    sigungu_code: row.sigungu_code.trim(),
    sigungu_name: row.sigungu_name,
    sido_code: row.sido_code.trim(),
    sido_name: row.sido_name,
  };
}
