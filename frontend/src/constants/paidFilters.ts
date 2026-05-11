/** 유료 분석 UI·API 매핑 — `pipeline/clean.py` 축약값과 DB `road_condition` 일치 */

export const ROAD_CONDITIONS = ["25이", "25미", "12미", "8미", "-"] as const;

export const AREA_CATEGORIES = ["광소", "정상", "광대"] as const;

/** 연도 버튼 5개: 올해 기준 Y-4 … Y (표시는 끝 두 자리) */
export function getPaidYearButtonYears(): readonly number[] {
  const Y = new Date().getFullYear();
  return [Y - 4, Y - 3, Y - 2, Y - 1, Y] as const;
}

/** 기본 선택: 최근 4년 (Y-3 ~ Y), 무료 사전집계 DEFAULT_YEARS_BACK=4와 같은 폭 */
export function getDefaultPaidSelectedYears(): number[] {
  const Y = new Date().getFullYear();
  return [Y - 3, Y - 2, Y - 1, Y];
}
