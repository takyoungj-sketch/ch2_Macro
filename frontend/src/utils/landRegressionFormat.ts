import type { LandRegressionCoeff } from "../types";

export const EQUATION_SIG_P = 0.1;

export function formatCoefValue(v: number): string {
  if (!Number.isFinite(v)) return "—";
  if (v !== 0 && Math.abs(v) < .00005) return v.toExponential(2);
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

/** 도로:8미만 → 8미만 */
export function shortDisplayLabel(label: string): string {
  let s = label.trim();
  s = s.replace(/\s*\(기준\s*대비\)\s*$/i, "");
  const prefixes = ["도로:", "도로 ", "유형:", "유형 ", "지역:", "지역 "];
  for (const p of prefixes) {
    if (s.startsWith(p) && s.length > p.length) {
      s = s.slice(p.length).trim();
      break;
    }
  }
  return s || label;
}

export function coefficientSortKey(name: string): [number, number, string] {
  if (name === "const") return [0, 0, name];
  if (name === "log_area") return [1, 0, name];
  if (name === "area_sqm") return [1, 1, name];
  if (name === "year_trend") return [2, 0, name];
  if (name === "log_assessed_land_price") return [2, 1, name];
  if (name.startsWith("road_")) return [3, 0, name];
  if (name.startsWith("deal_")) return [4, 0, name];
  if (name === "partial_own") return [5, 0, name];
  if (name.startsWith("beop_")) return [9, 0, name];
  return [8, 0, name];
}

export function compareCoefficientOrder(a: LandRegressionCoeff, b: LandRegressionCoeff): number {
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

export function sortCoefficientsByVariableOrder(coefficients: LandRegressionCoeff[]): LandRegressionCoeff[] {
  return [...coefficients].sort(compareCoefficientOrder);
}

export function countSignificantCoefficients(coefficients: LandRegressionCoeff[]): number {
  return coefficients.filter((c) => c.name !== "const" && isEquationSignificant(c.p)).length;
}

export const sigRowClass = "bg-emerald-50/90 text-emerald-900 font-medium";

function fmtPctFromLog(coef: number): string {
  const pct = Math.expm1(coef) * 100;
  if (!Number.isFinite(pct)) return "계산 범위 초과";
  const sign = pct >= 0 ? "+" : "−";
  const amount = pct !== 0 && Math.abs(pct) < .05 ? Math.abs(pct).toExponential(2) : Math.abs(pct).toFixed(1);
  return `${sign}${amount}%`;
}

function fmtUnitPrice(coef: number): string {
  const sign = coef >= 0 ? "+" : "−";
  const abs = Math.abs(coef);
  const amount = coef !== 0 && abs < .005 ? abs.toExponential(2) : abs.toLocaleString("ko-KR", { maximumFractionDigits: abs < 1 ? 2 : 0 });
  return `${sign}${amount}만원/㎡`;
}

/** 계수표 설명형 문구 (집합·복합 effect_plain 톤) */
export function interpretLandCoefficient(
  c: LandRegressionCoeff,
  modelType: "log" | "linear",
): string {
  const { name, coef } = c;

  if (name === "const") {
    if (modelType === "log") {
      return `로그 단가 상수 ${formatCoefValue(coef)} (다른 설명변수 0·기준 범주 전제)`;
    }
    return `기준 단가 출발 수준 ${formatCoefValue(coef)}만원/㎡ (다른 변수 0·기준 범주 전제)`;
  }

  if (name === "log_area" || name === "log_assessed_land_price") {
    const label = name === "log_area" ? "면적" : "개별공시지가";
    if (modelType === "log") {
      const pct = Math.expm1(coef * Math.log(1.01)) * 100;
      const sign = pct >= 0 ? "+" : "−";
      const amount = pct !== 0 && Math.abs(pct) < .005 ? Math.abs(pct).toExponential(2) : Math.abs(pct).toFixed(2);
      return `${label} 1% 증가 시 단가 약 ${sign}${amount}%`;
    }
    const delta = coef * Math.log(1.01);
    const sign = delta >= 0 ? "+" : "−";
    const abs = Math.abs(delta);
    const body = abs !== 0 && abs < .005 ? abs.toExponential(2) : abs >= 1 ? Math.round(abs).toLocaleString("ko-KR") : abs.toFixed(2);
    return `${label} 1% 증가 시 단가 ${sign}${body}만원/㎡`;
  }

  if (name === "area_sqm") {
    if (modelType === "log") return `1㎡ 증가 시 단가 약 ${fmtPctFromLog(coef)}`;
    return `1㎡ 증가 시 단가 ${fmtUnitPrice(coef)}`;
  }

  if (name === "year_trend") {
    if (modelType === "log") {
      return `연도 1년 진행(평균 대비) 시 단가 약 ${fmtPctFromLog(coef)}`;
    }
    return `연도 1년 진행 시 단가 ${fmtUnitPrice(coef)}`;
  }

  if (name === "partial_own") {
    if (modelType === "log") {
      return `지분거래 시 단가 약 ${fmtPctFromLog(coef)} (전체면적 거래 대비)`;
    }
    return `지분거래 시 단가 ${fmtUnitPrice(coef)} (전체면적 거래 대비)`;
  }

  if (modelType === "log") {
    return `기준 대비 약 ${fmtPctFromLog(coef)}`;
  }
  return `기준 대비 ${fmtUnitPrice(coef)}`;
}
