/** 유료 분석 UI·API 매핑 — `pipeline/clean.py` 축약값과 DB `road_condition` 일치 */

export const ROAD_CONDITIONS = ["25이", "25미", "12미", "8미", "-"] as const;

export const AREA_CATEGORIES = ["광소", "정상", "광대"] as const;

/** 연도 버튼 5개: 올해 기준 Y-5 … Y-1 (당해 연도 제외, 보통 DB 적재 구간과 맞춤) */
export function getPaidYearButtonYears(): readonly number[] {
  const Y = new Date().getFullYear();
  return [Y - 5, Y - 4, Y - 3, Y - 2, Y - 1] as const;
}

/** 기본 선택: 최근 4년 (Y-4 ~ Y-1). 예: 2026년 → 22~25년 체크 */
export function getDefaultPaidSelectedYears(): number[] {
  const Y = new Date().getFullYear();
  return [Y - 4, Y - 3, Y - 2, Y - 1];
}
