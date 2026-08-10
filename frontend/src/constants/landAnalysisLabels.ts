import type { FreeStatsWindowYears } from "../types";

/** contract_date 기준 롤링 창 — 기본 통계·무료 조회 */
export function rollingStatsCaption(windowYears: FreeStatsWindowYears): string {
  return `${windowYears}년 롤링`;
}

/** contract_year(만년력) + 사용자 필터 — 필터 분석 */
export const calendarYearFilterCaption = "만년력";

export function basicStatsActionLabel(viewMode: "free" | "paid"): string {
  return viewMode === "free" ? "무료 통계 조회" : "기본 통계 보기";
}

export const filteredAnalysisActionLabel = "필터 분석 실행";

export function filteredAnalysisResultTitle(): string {
  return `필터 분석 결과 · ${calendarYearFilterCaption}`;
}
