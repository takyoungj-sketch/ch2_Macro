import type { RegionalRegressionPredictInputs } from "../api/regionalRegressionClient";

/** 단지 원자료의 구조·시공사명을 현재 모형의 희소 범주 분류에 맞춘다. */
export function regionalPredictionCategories(
  inputs: RegionalRegressionPredictInputs,
  options: Record<string, string[]> = {},
): RegionalRegressionPredictInputs {
  const result = { ...inputs };
  for (const key of ["structure_group", "builder_group"] as const) {
    const allowed = options[key] ?? [];
    if (!allowed.length) continue;
    const raw = inputs[key]?.trim() ?? "";
    const value = ["", "nan", "none", "null", "(null)", "(미상)", "미상"].includes(raw.toLowerCase()) ? "미상" : raw;
    if (allowed.includes(value)) result[key] = value;
    else if (value !== "미상" && allowed.includes("기타")) result[key] = "기타";
  }
  return result;
}
