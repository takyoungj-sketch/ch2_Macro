/** 유료 분석 UI·API 매핑 — `pipeline/clean.py` 축약값과 DB `road_condition` 일치 */

export const ROAD_CONDITIONS = ["25이", "25미", "12미", "8미", "-"] as const;

export const AREA_CATEGORIES = ["광소", "정상", "광대"] as const;

/** 연도 버튼 5개: 올해 기준 Y-5 … Y-1 (당해 연도 제외, 보통 DB 적재 구간과 맞춤) */
export function getPaidYearButtonYears(): readonly number[] {
  const Y = new Date().getFullYear();
  return [Y - 5, Y - 4, Y - 3, Y - 2, Y - 1] as const;
}

/** 기본 선택: 연도 버튼과 동일하게 Y-5 ~ Y-1 전부 포함 (예: 2026년 기준 → 2021~2025 체크) */
export function getDefaultPaidSelectedYears(): number[] {
  return [...getPaidYearButtonYears()];
}

/** 기본 통계 API의 year_from∼year_to (사전집계 창)과 같은 연도 목록 */
export function yearsRangeInclusive(yearFrom: number, yearTo: number): number[] {
  const yf = Number(yearFrom);
  const yt = Number(yearTo);
  if (!Number.isFinite(yf) || !Number.isFinite(yt) || yf > yt) return [];
  const out: number[] = [];
  for (let y = yf; y <= yt; y += 1) out.push(y);
  return out;
}
