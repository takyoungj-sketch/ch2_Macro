/** 회귀식·계수 표 — 표시 유틸 */

import type { RegressionCoeff } from "../types";

export const EQUATION_SIG_P = 0.1;

export function formatCoefValue(v: number): string {
  if (Math.abs(v) >= 100) {
    return v.toLocaleString("ko-KR", { maximumFractionDigits: 0 });
  }
  if (Math.abs(v) >= 1) {
    return v.toLocaleString("ko-KR", { maximumFractionDigits: 1 }).replace(/\.0$/, "");
  }
  const s = v.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  return s;
}

export function fmtDecimal(v: number | null | undefined, digits = 5): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

export function isEquationSignificant(p: number | null | undefined): boolean {
  return p != null && p < EQUATION_SIG_P;
}

/** 용도지역 제3종…(기준 대비) → 제3종… */
export function shortDisplayLabel(label: string): string {
  let s = label.trim();
  s = s.replace(/\s*\(기준\s*대비\)\s*$/i, "");
  const prefixes = ["용도지역 ", "건축물용도 ", "도로폭 ", "동 ", "권리 ", "단지 ", "시공사 ", "구조 ", "유형 "];
  for (const p of prefixes) {
    if (s.startsWith(p) && s.length > p.length) {
      s = s.slice(p.length).trim();
      break;
    }
  }
  if (s.startsWith("층 ") && s.length > 2) {
    s = s.slice(2).trim();
  }
  return s || label;
}

/** 회귀식·계수표 공통 변수 순서 (면적 → 연식 → 층 → 동 → 기타) */
export function coefficientSortKey(name: string): [number, number, string] {
  if (name === "const") return [0, 0, name];
  if (name === "exclusive_area") return [1, 0, name];
  if (name === "gross_area") return [1, 1, name];
  if (name === "land_area") return [1, 2, name];
  if (name === "building_age") return [2, 0, name];
  if (name === "households" || name === "ln_households") return [2, 1, name];
  if (name === "max_floor") return [3, -1, name];
  if (name === "parking_per_household") return [3, -1, name];
  if (name === "floor") return [3, 0, name];
  if (name.startsWith("floor_rel_")) return [3, 1, name];
  if (name.startsWith("floor_grp_")) return [3, 2, name];
  if (name.startsWith("floor_")) return [3, 3, name];
  if (name.startsWith("dong_")) return [4, 0, name];
  if (name.startsWith("addr4_")) return [4, 1, name];
  if (name.startsWith("rights_")) return [5, 0, name];
  if (name.startsWith("atype_")) return [5, 5, name];
  if (name.startsWith("zone_")) return [6, 0, name];
  if (name.startsWith("use_")) return [6, 1, name];
  if (name.startsWith("roadw_")) return [6, 2, name];
  if (name === "road_code") return [6, 3, name];
  if (name.startsWith("struct_")) return [6, 4, name];
  if (name.startsWith("builder_")) return [6, 5, name];
  if (name.startsWith("bld_")) return [9, 0, name];
  return [8, 0, name];
}

export function compareCoefficientOrder(a: RegressionCoeff, b: RegressionCoeff): number {
  const ka = coefficientSortKey(a.name);
  const kb = coefficientSortKey(b.name);
  for (let i = 0; i < 3; i++) {
    if (ka[i] !== kb[i]) {
      if (typeof ka[i] === "string") {
        return String(ka[i]).localeCompare(String(kb[i]));
      }
      return (ka[i] as number) - (kb[i] as number);
    }
  }
  return 0;
}

export function sortCoefficientsByVariableOrder(coefficients: RegressionCoeff[]): RegressionCoeff[] {
  return [...coefficients].sort(compareCoefficientOrder);
}

export function countSignificantCoefficients(coefficients: RegressionCoeff[]): number {
  return coefficients.filter((c) => c.name !== "const" && isEquationSignificant(c.p)).length;
}

export const sigRowClass =
  "bg-emerald-50/90 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-100 font-medium";
