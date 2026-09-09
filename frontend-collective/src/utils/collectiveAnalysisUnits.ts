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

export type CollectiveRegionScope = {
  region_codes?: string[];
  region_code_level?: CollectiveAnalysisLevel;
  region_addrs?: string[];
};

export type CollectiveUserFilterFields = {
  assetType: string;
  addr1: string;
  addr2: string;
  hasIntermediate: boolean;
  guList: string[];
  leafList: string[];
  yearFrom: number | "";
  yearTo: number | "";
  windowYears: number;
  sort: string;
};

function listKey(xs?: readonly string[]): string {
  return JSON.stringify(xs ?? []);
}

export function unitsToRegionScope(units: CollectiveAnalysisUnit[]): CollectiveRegionScope {
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

/** 왼쪽 필터(유형·지역·연도·정렬)가 마지막 통계분석 스냅샷과 다른지. */
export function isCollectiveUserFilterStale(
  scope: CollectiveUserFilterFields,
  live: CollectiveUserFilterFields,
): boolean {
  return (
    scope.assetType !== live.assetType ||
    scope.addr1 !== live.addr1 ||
    scope.addr2 !== live.addr2 ||
    scope.hasIntermediate !== live.hasIntermediate ||
    listKey(scope.guList) !== listKey(live.guList) ||
    listKey(scope.leafList) !== listKey(live.leafList) ||
    scope.yearFrom !== live.yearFrom ||
    scope.yearTo !== live.yearTo ||
    scope.windowYears !== live.windowYears ||
    scope.sort !== live.sort
  );
}

/**
 * 행정코드 resolve가 실행 직후 뒤늦게 채워진 경우.
 * 사용자가 칩·지도 인접을 바꾼 뒤(이미 코드가 있는 스냅샷에서 가감)는 false.
 */
export function isCollectiveRegionScopeHydration(
  snap: CollectiveRegionScope,
  live: CollectiveRegionScope,
): boolean {
  const sc = snap.region_codes ?? [];
  const lc = live.region_codes ?? [];
  const sa = snap.region_addrs ?? [];
  const la = live.region_addrs ?? [];
  if (listKey(sc) === listKey(lc) && listKey(sa) === listKey(la)) return false;
  if (sc.length === 0 && lc.length > 0) return true;
  if (sa.length === 0 && la.length > 0 && listKey(sc) === listKey(lc)) return true;
  return false;
}

export function isCollectiveRegionScopeStale(
  snap: CollectiveRegionScope,
  live: CollectiveRegionScope,
): boolean {
  if (listKey(snap.region_codes) === listKey(live.region_codes) && listKey(snap.region_addrs) === listKey(live.region_addrs)) {
    return false;
  }
  return !isCollectiveRegionScopeHydration(snap, live);
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
