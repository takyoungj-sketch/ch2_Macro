import { MAX_V2_STATS_BULK_CODES } from "../constants/v2BulkLimits";
import type { RegionLevel } from "../types";

export type UpperSingleSelection = { level: RegionLevel; code: string };

/** `/free/v2/stats/bulk` 코드 한도 초과 여부 — 백엔드 `_MAX_STATS_REGIONS` 와 동일. */
export function exceedsV2BulkLimit(resolvedCount: number): boolean {
  return resolvedCount > MAX_V2_STATS_BULK_CODES;
}

/** 복수 법정단위 bulk 선조회 사용 여부 (상위 단일 선택·한도 초과 시 false). */
export function shouldUseBulkStats(
  resolvedCount: number,
  upperSingle: UpperSingleSelection | null
): boolean {
  return resolvedCount > 1 && upperSingle == null && !exceedsV2BulkLimit(resolvedCount);
}

/** 필터 분석 — bulk 생략·upper/원장 실시간 전환 안내 (「실패」 문구 없음). */
export function filteredAnalysisScopeNoticeOverBulkLimit(
  resolvedCount: number,
  upperSingle: UpperSingleSelection | null
): string {
  const n = resolvedCount.toLocaleString();
  if (upperSingle != null) {
    return `법정동·리 ${n}곳(${MAX_V2_STATS_BULK_CODES}곳 초과) — 상위 행정구역 사전집계와 원장 실시간 집계로 전환했습니다.`;
  }
  return `법정동·리 ${n}곳(${MAX_V2_STATS_BULK_CODES}곳 초과) — 원장 실시간 집계로 전환했습니다.`;
}
