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
