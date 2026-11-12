/** 유료 분석 UI·API 매핑 — `pipeline/clean.py` 축약값과 DB `road_condition` 일치 */

import type { FreeStatsWindowYears } from "../types";

export const ROAD_CONDITIONS = ["25이상", "25미만", "12미만", "8미만", "-"] as const;

export const AREA_CATEGORIES = ["광소", "정상", "광대"] as const;

/** 계약면적 기준. pipeline/constants.py AREA_CATEGORIES 와 같다. */
export const AREA_CATEGORY_LABELS: Record<(typeof AREA_CATEGORIES)[number], string> = {
  광소: "광소(30㎡ 미만)",
  정상: "정상",
  광대: "광대(3000㎡ 이상)",
};

export const DEAL_TYPES = ["중개거래", "직거래"] as const;

/**
 * 롤링 창 길이로부터 필터에 표시할 달력 연도 후보를 구한다.
 * 실제 필터 선택은 기본통계 창과 별도로 관리한다.
 */
export function getPaidYearButtonYears(
  windowYears: FreeStatsWindowYears = 5,
): readonly number[] {
  const Y = new Date().getFullYear();
  const start = Y - windowYears;
  const out: number[] = [];
  for (let y = start; y <= Y; y += 1) out.push(y);
  return out;
}

/** 기본 선택: 해당 창의 연도 칩 전부 포함 */
export function getDefaultPaidSelectedYears(
  windowYears: FreeStatsWindowYears = 5,
): number[] {
  return [...getPaidYearButtonYears(windowYears)];
}
