import type { RegionItem, TwinEupAnchor, TwinSigunguAnchor, TwinV8Query } from "../types";

/** Twin v8 Phase 1 — 충청권 시도 코드 (pipeline/twin_v8/scoring.py 와 동일) */
export const CHUNGCHEONG_SIDO_CODES = new Set(["30", "36", "43", "44"]);

function isBeopjungriRi(row: RegionItem): boolean {
  const code = row.beopjungri_code.trim();
  if (code.length === 10 && !code.endsWith("00")) return true;
  return row.beopjungri_name.trim().endsWith("리");
}

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

/**
 * Twin v8 조회용 앵커 — 단일 리 → beopjungri, 단일 읍면동 → eupmyeondong, 단일 시군구 → sigungu.
 */
export function resolveTwinV8Query(
  regions: RegionItem[],
  resolvedBeopjungriCodes: string[],
): TwinV8Query | null {
  const wants = new Set(resolvedBeopjungriCodes.map((c) => c.trim()).filter(Boolean));
  if (wants.size === 0) return null;

  const matches = regions.filter((r) => wants.has(r.beopjungri_code.trim()));
  const matchedBeop = new Set(matches.map((m) => m.beopjungri_code.trim()));
  for (const c of wants) {
    if (!matchedBeop.has(c)) return null;
  }

  if (wants.size === 1) {
    const row = matches[0]!;
    if (isBeopjungriRi(row)) {
      return {
        region_level: "beopjungri",
        region_code: row.beopjungri_code.trim(),
        region_name: row.beopjungri_name,
        sido_code: row.sido_code.trim(),
        sido_name: row.sido_name,
        sigungu_name: row.sigungu_name,
      };
    }
  }

  const eup = resolveTwinAnchorEupmyeondong(regions, resolvedBeopjungriCodes);
  if (eup) {
    return {
      region_level: "eupmyeondong",
      region_code: eup.eupmyeondong_code,
      region_name: eup.eupmyeondong_name,
      sido_code: eup.sido_code,
      sido_name: eup.sido_name,
      sigungu_name: eup.sigungu_name,
    };
  }

  const sg = resolveTwinAnchorSigungu(regions, resolvedBeopjungriCodes);
  if (sg) {
    return {
      region_level: "sigungu",
      region_code: sg.sigungu_code,
      region_name: sg.sigungu_name,
      sido_code: sg.sido_code,
      sido_name: sg.sido_name,
      sigungu_name: sg.sigungu_name,
    };
  }

  return null;
}

export function isChungcheongSido(sidoCode: string): boolean {
  return CHUNGCHEONG_SIDO_CODES.has(sidoCode.trim().slice(0, 2));
}
