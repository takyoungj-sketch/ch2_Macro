/** 복합 분석 scope 단위 — 교차 시군구 인접 복수용. */

export type BuiltAnalysisLevel = "eupmyeondong" | "beopjungri";

export type BuiltAnalysisUnit = {
  code: string;
  level: BuiltAnalysisLevel;
  name: string;
  addr1: string;
  addr2: string;
  /** beopjungri 시 상위 읍·면 이름 */
  eup?: string;
  /** 지도로 추가한 타 시군구 — resolve 동기화가 지우지 않음 */
  crossParent?: boolean;
};

export const MAX_BUILT_ANALYSIS_UNITS = 10;

export function analysisUnitLabel(u: BuiltAnalysisUnit): string {
  const parent = (u.addr2 || "").trim();
  const name = (u.name || "").trim();
  if (u.level === "beopjungri" && u.eup) {
    const base = parent ? `${parent} ${u.eup} ${name}` : `${u.eup} ${name}`;
    return base.trim();
  }
  if (parent && name && parent !== name) return `${parent} ${name}`;
  return name || parent || u.code;
}

/** API용 '시도|시군구|읍면동|리' 키 — 코드 NULL 원장 행 포함 */
export function unitToAddrKey(u: BuiltAnalysisUnit): string | null {
  const a1 = (u.addr1 || "").trim();
  const a2 = (u.addr2 || "").trim();
  let leaf = (u.name || "").trim();
  // resolve 라벨 누락 시 name=code 로 들어오는 경우 addr 매칭에 쓰지 않음
  if (/^\d{8,10}$/.test(leaf)) leaf = "";
  if (!a1 || !a2 || !leaf) return null;
  return `${a1}|${a2}|${leaf}`;
}

export function unitsToRegionScope(units: BuiltAnalysisUnit[]): {
  region_codes?: string[];
  region_code_level?: BuiltAnalysisLevel;
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
