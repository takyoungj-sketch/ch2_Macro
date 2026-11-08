import type { FloorIndexCell } from "../types";

export const UTILITY_CONTROL_LABELS: Record<string, string> = {
  ln_exclusive_area: "전용면적(로그)", ln_gross_area: "연면적(로그)", building_age: "연식",
  relative_floor: "상대층", rowhouse_floor: "연립 층 구간", contract_period: "거래시점(반기)",
  building_fixed_effects: "단지별 차이", shop_floor: "상가 층 구간", factory_floor: "공장 층 구간",
};

export function utilityNumber(value?: number | null, digits = 1) {
  return value != null && Number.isFinite(value)
    ? value.toLocaleString("ko-KR", { maximumFractionDigits: digits }) : "—";
}

export function utilityP(value?: number | null) {
  if (value == null || !Number.isFinite(value)) return "—";
  if (value < 0.001) return "<0.001";
  return value.toLocaleString("ko-KR", { maximumFractionDigits: 3 });
}

export function utilityWarnings(warnings: string[] = []) {
  const unique = [...new Set(warnings)];
  const groupMissing = (text: string) => /표본 부족으로 회귀에서 제외|최종 회귀 표본에 남지 않아/.test(text);
  const variableNote = (text: string) => /통제에서 (뺐|제외)|통제를 뺐|동은 단지별로 나눕니다/.test(text);
  const collinearity = (text: string) => /다중공선성|설계행렬 조건수/.test(text);
  return {
    important: unique.filter(text => !groupMissing(text) && !variableNote(text) && !collinearity(text)),
    hasExcludedControls: unique.some(variableNote),
    hasCollinearity: unique.some(collinearity),
  };
}

export function unavailableUtilityReason(cell: FloorIndexCell, warnings: string[] = []) {
  const message = warnings.find(text => text.startsWith(`${cell.label} `));
  if (message?.includes("표본 부족")) return "거래 부족";
  if (message?.includes("최종 회귀 표본")) return "분석 거래 부족";
  return cell.count === 0 ? "분석 거래 없음" : "추정 불가";
}
