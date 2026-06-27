import type { AssetType } from "../types";

const COEF_LABELS: Record<string, string> = {
  const: "상수(절편)",
  gross_area: "연면적",
  land_area: "대지면적",
  building_age: "연식",
  road_code: "도로",
};

const ASSET_TYPE_LABELS: Record<string, string> = {
  commercial: "상업",
  factory: "공장",
  detached: "단독",
};

export { ASSET_TYPE_LABELS };

/** statsmodels 변수명 → 표시용 한글 */
export function formatCoefName(name: string, assetType?: AssetType): string {
  if (COEF_LABELS[name]) return COEF_LABELS[name];
  if (name.startsWith("zone_")) return `용도지역·${name.slice(5)}`;
  if (name.startsWith("use_")) {
    const prefix = assetType === "detached" ? "주택유형" : "건축물용도";
    return `${prefix}·${name.slice(4)}`;
  }
  if (name.startsWith("road_")) return `도로조건·${name.slice(5)}`;
  if (name.startsWith("atype_")) {
    const key = name.slice(6);
    return `유형·${ASSET_TYPE_LABELS[key] ?? key}`;
  }
  if (name.startsWith("loc_")) return `지역·${name.slice(4)}`;
  return name;
}

export function formatCoefValue(v: number): string {
  if (Math.abs(v) >= 100) return v.toLocaleString("ko-KR", { maximumFractionDigits: 0 });
  if (Math.abs(v) >= 1) {
    return v.toLocaleString("ko-KR", { maximumFractionDigits: 1 }).replace(/\.0$/, "");
  }
  const s = v.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  return s;
}

export const ADMIN_LABELS: Record<string, string> = {
  sigungu: "시군구",
  gu: "구",
  eupmyeondong: "읍면동",
  beopjungri: "법정리",
};

export function levelCardTitle(scopeLabel: string | null | undefined, adminLevel: string): string {
  const sl = scopeLabel?.trim();
  if (!sl) return ADMIN_LABELS[adminLevel] ?? adminLevel;
  if (sl.endsWith(" 시군구")) return sl.slice(0, -" 시군구".length);
  if (sl.endsWith(" 읍면동")) return sl.slice(0, -" 읍면동".length);
  if (sl.endsWith(" 읍·면")) return sl.slice(0, -" 읍·면".length);
  return sl;
}

export function fmtNum(n?: number | null, digits = 0) {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("ko-KR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function fmtDecimal(n?: number | null, digits = 5) {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toFixed(digits);
}

export function fmtCoefInt(n?: number | null) {
  if (n == null || Number.isNaN(n)) return "—";
  return Math.round(n).toLocaleString("ko-KR");
}

/** 회귀식 표시용 유의 수준 — 일반 계수표(0.05)보다 lenient */
export const EQUATION_SIG_P = 0.1;

export function isEquationSignificant(pValue: number | null | undefined): boolean {
  return pValue != null && pValue < EQUATION_SIG_P;
}
