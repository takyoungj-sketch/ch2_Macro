import type { PaidAnalysisRequest } from "../types";
import { mergePaidExcludedIntoRequest } from "./paidFiltersMap";

export function buildPaidPayload(
  paidRequest: PaidAnalysisRequest,
  regionCodes: string[],
  roadExcluded: readonly string[],
  areaExcluded: readonly string[],
  baseCacheKey?: string | null
): PaidAnalysisRequest {
  const merged = mergePaidExcludedIntoRequest(paidRequest, roadExcluded, areaExcluded);
  const ys = merged.years;
  const useYears = ys != null && ys.length > 0;
  return {
    ...merged,
    region_codes: regionCodes.length > 0 ? regionCodes : null,
    region_selections: null,
    base_cache_key: baseCacheKey ?? null,
    year_from: useYears ? null : merged.year_from,
    year_to: useYears ? null : merged.year_to,
    years: useYears ? [...ys].sort((a, b) => a - b) : merged.years,
  };
}

/** 필터 분석 모달: 기본통계 V2 롤링(contract_date 버킷) 필드 제거 후 연도·필터만 사용 */
export function clearRollingMatrixFields(
  req: PaidAnalysisRequest
): PaidAnalysisRequest {
  return {
    ...req,
    rolling_matrix_period_start: null,
    rolling_matrix_period_end: null,
    rolling_bucket_count: null,
    rolling_stats_reference_date: null,
  };
}
