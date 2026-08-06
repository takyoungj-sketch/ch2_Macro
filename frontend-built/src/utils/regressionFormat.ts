import type { AssetType, RegressionCoeff, ResponseScale } from "../types";

const COEF_LABELS: Record<string, string> = {
  const: "절편",
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

/** statsmodels 변수명 → 표시용 한글 (맥락 유지) */
export function formatCoefName(name: string, assetType?: AssetType, responseScale?: ResponseScale): string {
  if (COEF_LABELS[name]) {
    const base = COEF_LABELS[name];
    if (responseScale === "loglog" && (name === "gross_area" || name === "land_area")) {
      return `log(${base})`;
    }
    return base;
  }
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

/** 회귀식·계수표용 짧은 변수명 — 용도지역·제3종… → 제3종… */
export function shortCoefName(name: string, assetType?: AssetType, responseScale?: ResponseScale): string {
  if (name === "const") return "절편";
  if (name in COEF_LABELS && name !== "const") {
    const base = COEF_LABELS[name];
    if (responseScale === "loglog" && (name === "gross_area" || name === "land_area")) {
      return `log(${base})`;
    }
    return base;
  }
  if (name.startsWith("zone_")) return name.slice(5);
  if (name.startsWith("use_")) return name.slice(4);
  if (name.startsWith("road_")) return name.slice(5);
  if (name.startsWith("atype_")) {
    const key = name.slice(6);
    return ASSET_TYPE_LABELS[key] ?? key;
  }
  if (name.startsWith("loc_")) return name.slice(4);
  return formatCoefName(name, assetType);
}

/** 라벨 문자열에서 접두·(기준 대비) 제거 */
export function shortDisplayLabel(label: string): string {
  let s = label.trim();
  s = s.replace(/\s*\(기준\s*대비\)\s*$/i, "");
  const prefixes = [
    "용도지역·",
    "용도지역 ",
    "건축물용도·",
    "건축물용도 ",
    "주택유형·",
    "주택유형 ",
    "도로조건·",
    "도로조건 ",
    "도로폭 ",
    "유형·",
    "유형 ",
    "지역·",
    "지역 ",
  ];
  for (const p of prefixes) {
    if (s.startsWith(p) && s.length > p.length) {
      s = s.slice(p.length).trim();
      break;
    }
  }
  return s || label;
}

const CONTINUOUS_NAMES = new Set(["gross_area", "land_area", "building_age", "road_code"]);

function isContinuousCoef(name: string): boolean {
  return CONTINUOUS_NAMES.has(name);
}

function unitSuffix(name: string): string {
  if (name === "gross_area" || name === "land_area") return "㎡";
  if (name === "building_age") return "년";
  if (name === "road_code") return "m";
  return "";
}

function fmtManwon(v: number): string {
  const sign = v >= 0 ? "+" : "−";
  return `${sign}${Math.abs(Math.round(v)).toLocaleString("ko-KR")}만원`;
}

function fmtPctFromLog(coef: number): string {
  const pct = (Math.exp(coef) - 1) * 100;
  const sign = pct >= 0 ? "+" : "−";
  return `${sign}${Math.abs(pct).toFixed(1)}%`;
}

/** 계수표 설명형 문구 (집합부동산 effect_plain과 동일 톤) */
export function interpretCoefficient(
  c: RegressionCoeff,
  responseScale: ResponseScale,
  _assetType?: AssetType,
): string {
  const name = c.name;
  const coef = c.estimate;
  const usesLogY = responseScale === "log" || responseScale === "loglog";
  if (name === "const") {
    if (usesLogY) {
      const approx = Math.exp(coef);
      return `기준 조건 log(금액) 출발점 (대략 ${Math.round(approx).toLocaleString("ko-KR")}만원 수준, 다른 변수·기준 범주 전제)`;
    }
    return `기준 조건 출발 수준 약 ${Math.round(coef).toLocaleString("ko-KR")}만원 (다른 변수 0·기준 범주 전제)`;
  }

  const unit = unitSuffix(name);
  const step = unit ? `1${unit} ` : "1단위 ";

  if (responseScale === "loglog" && (name === "gross_area" || name === "land_area")) {
    const pct = (Math.pow(1.01, coef) - 1) * 100;
    const sign = pct >= 0 ? "+" : "−";
    return `면적 1% 증가 시 금액 약 ${sign}${Math.abs(pct).toFixed(2)}% (탄력성 ≈ ${coef.toFixed(3)})`;
  }

  if (responseScale === "log") {
    const pct = fmtPctFromLog(coef);
    if (isContinuousCoef(name)) return `${step}증가 시 금액 약 ${pct}`;
    return `기준 대비 약 ${pct}`;
  }

  if (isContinuousCoef(name)) return `${step}증가 시 ${fmtManwon(coef)}`;
  return `기준 대비 ${fmtManwon(coef)}`;
}

export function coefficientSortKey(name: string): [number, number, string] {
  if (name === "const") return [0, 0, name];
  if (name === "gross_area") return [1, 0, name];
  if (name === "land_area") return [1, 1, name];
  if (name === "building_age") return [2, 0, name];
  if (name === "road_code") return [2, 1, name];
  if (name.startsWith("zone_")) return [6, 0, name];
  if (name.startsWith("use_")) return [6, 1, name];
  if (name.startsWith("road_")) return [6, 2, name];
  if (name.startsWith("atype_")) return [6, 3, name];
  if (name.startsWith("loc_")) return [7, 0, name];
  return [8, 0, name];
}

export function compareCoefficientOrder(a: RegressionCoeff, b: RegressionCoeff): number {
  const ka = coefficientSortKey(a.name);
  const kb = coefficientSortKey(b.name);
  for (let i = 0; i < 3; i++) {
    if (ka[i] !== kb[i]) {
      if (typeof ka[i] === "string") return String(ka[i]).localeCompare(String(kb[i]));
      return (ka[i] as number) - (kb[i] as number);
    }
  }
  return 0;
}

export function sortCoefficientsByVariableOrder(coefficients: RegressionCoeff[]): RegressionCoeff[] {
  return [...coefficients].sort(compareCoefficientOrder);
}

export const sigRowClass =
  "bg-emerald-50/90 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-100 font-medium";

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

export function countSignificantCoefficients(coefficients: RegressionCoeff[]): number {
  return coefficients.filter((c) => c.name !== "const" && isEquationSignificant(c.p_value)).length;
}
