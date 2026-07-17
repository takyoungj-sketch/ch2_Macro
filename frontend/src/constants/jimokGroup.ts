/** 지목군 7분류 — docs/LAND_JIMOK_GROUP_DESIGN.md / D-026 */
export type MatrixMode = "category" | "group";

export const JIMOK_GROUP_ORDER: ReadonlyArray<{ code: string; label: string }> = [
  { code: "agri", label: "농경지" },
  { code: "forest", label: "산림지" },
  { code: "dev", label: "개발지" },
  { code: "infra", label: "기반시설" },
  { code: "water", label: "수면" },
  { code: "special", label: "특수용도" },
  { code: "other", label: "기타" },
];

export const MATRIX_MODE_LABEL: Record<MatrixMode, string> = {
  category: "용도 × 지목",
  group: "용도 × 지목군",
};
