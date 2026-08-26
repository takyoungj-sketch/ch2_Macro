/** 집합 분석 scope 단위 — 교차 시군구 인접 복수용. 복합 `builtAnalysisUnits` 와 동일 모델. */

export type CollectiveAnalysisLevel = "eupmyeondong" | "beopjungri";

export type CollectiveAnalysisUnit = {
  code: string;
  level: CollectiveAnalysisLevel;
  name: string;
  addr1: string;
  addr2: string;
  /** beopjungri 시 상위 읍·면 이름 */
  eup?: string;
  /** 지도로 추가한 타 시군구 — resolve 동기화가 지우지 않음 */
  crossParent?: boolean;
};

export const MAX_COLLECTIVE_ANALYSIS_UNITS = 10;

export function analysisUnitLabel(u: CollectiveAnalysisUnit): string {
  const parent = (u.addr2 || "").trim();
  const name = (u.name || "").trim();
  if (u.level === "beopjungri" && u.eup) {
    const base = parent ? `${parent} ${u.eup} ${name}` : `${u.eup} ${name}`;
    return base.trim();
  }
  if (parent && name && parent !== name) return `${parent} ${name}`;
  return name || parent || u.code;
}

export function unitToAddrKey(u: CollectiveAnalysisUnit): string | null {
  const a1 = (u.addr1 || "").trim();
  const a2 = (u.addr2 || "").trim();
  let leaf = (u.name || "").trim();
  if (/^\d{8,10}$/.test(leaf)) leaf = "";
  if (!a1 || !a2 || !leaf) return null;
  return `${a1}|${a2}|${leaf}`;
}

export function unitsToRegionScope(units: CollectiveAnalysisUnit[]): {
  region_codes?: string[];
  region_code_level?: CollectiveAnalysisLevel;
  region_addrs?: string[];
} {
  if (!units.length) return {};
  const level = units[0]!.level;
  const sameLevel = units.filter((u) => u.level === level);
  const codes = sameLevel.map((u) => u.code).filter(Boolean);
  const region_addrs = sameLevel
    .map(unitToAddrKey)
    .filter((k): k is string => Boolean(k));
  if (!codes.length && !region_addrs.length) return {};
  return {
    ...(codes.length ? { region_codes: codes, region_code_level: level } : { region_code_level: level }),
    ...(region_addrs.length ? { region_addrs } : {}),
  };
}

export function resolveCollectiveAnchorUnit(
  units: CollectiveAnalysisUnit[],
): CollectiveAnalysisUnit | null {
  const withCode = units.filter((u) => u.code && !u.crossParent);
  return withCode[0] ?? null;
}

export function anchorRegionCode(units: CollectiveAnalysisUnit[]): string | undefined {
  const anchor = resolveCollectiveAnchorUnit(units);
  if (!anchor?.code) return undefined;
  const digits = anchor.code.replace(/\D/g, "");
  return digits || undefined;
}
