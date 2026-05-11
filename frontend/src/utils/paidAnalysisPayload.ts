import type { PaidAnalysisRequest } from "../types";
import { mergePaidExcludedIntoRequest } from "./paidFiltersMap";

export function buildPaidPayload(
  paidRequest: PaidAnalysisRequest,
  regionCodes: string[],
  roadExcluded: readonly string[],
  areaExcluded: readonly string[]
): PaidAnalysisRequest {
  const merged = mergePaidExcludedIntoRequest(paidRequest, roadExcluded, areaExcluded);
  return {
    ...merged,
    region_codes: regionCodes.length > 0 ? regionCodes : null,
    region_selections: null,
  };
}
