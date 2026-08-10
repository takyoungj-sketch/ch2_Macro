/** 유료 분석 UI·API 매핑 — `pipeline/clean.py` 축약값과 DB `road_condition` 일치 */

import type { FreeStatsWindowYears } from "../types";

export const ROAD_CONDITIONS = ["25이상", "25미만", "12미만", "8미만", "-"] as const;

export const AREA_CATEGORIES = ["광소", "정상", "광대"] as const;

export const DEAL_TYPES = ["중개거래", "직거래"] as const;

/**
 * 필터 분석 연도 칩 — 기본통계 롤링 창(windowYears)과 맞춘 달력 연도.
 * as_of가 연중(예: 7월)이면 창에 걸치는 연도는 windowYears+1개 (5년 창 → 6칩, 7년 → 8칩).
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

/** 기본 통계(무료 V2)의 period_start∼period_end 가 걸치는 달력 연도 범위와 같은 연도 목록 */
export function yearsRangeInclusive(yearFrom: number, yearTo: number): number[] {
  const yf = Number(yearFrom);
  const yt = Number(yearTo);
  if (!Number.isFinite(yf) || !Number.isFinite(yt) || yf > yt) return [];
  const out: number[] = [];
  for (let y = yf; y <= yt; y += 1) out.push(y);
  return out;
}
