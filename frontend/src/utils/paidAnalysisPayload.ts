import type { MatrixYearlyRequest, PaidAnalysisRequest } from "../types";
import { mergePaidExcludedIntoRequest } from "./paidFiltersMap";

export function buildPaidPayload(
  paidRequest: PaidAnalysisRequest,
  regionCodes: string[],
  roadExcluded: readonly string[],
  areaExcluded: readonly string[],
  dealTypeExcluded: readonly string[] = [],
  baseCacheKey?: string | null
): PaidAnalysisRequest {
  const merged = mergePaidExcludedIntoRequest(
    paidRequest,
    roadExcluded,
    areaExcluded,
    dealTypeExcluded,
  );
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

export function buildPaidMatrixCellRequest(
  applied: PaidAnalysisRequest,
  zoneType: string,
  landCategory: string,
): MatrixYearlyRequest {
  return {
    ...applied,
    // 서버가 실제로 펼친 법정코드 범위를 재사용한다.
    region_selections: applied.region_codes?.length ? null : applied.region_selections,
    zone_type: zoneType,
    land_category: landCategory,
  };
}

/** 지역·캐시 키·매트릭스 축은 별도 상태다. 편집 가능한 분석 조건만 비교한다. */
export function paidFilterSignature(req: PaidAnalysisRequest): string {
  const rolling = Boolean(req.rolling_matrix_period_start && req.rolling_matrix_period_end);
  return JSON.stringify({
    period: rolling
      ? ["rolling", req.rolling_matrix_period_start, req.rolling_matrix_period_end]
      : req.years?.length ? ["years", ...req.years] : ["year-range", req.year_from ?? null, req.year_to ?? null],
    roads: req.road_conditions ?? null,
    areaCategories: req.area_categories ?? null,
    areaRange: [req.area_sqm_min ?? null, req.area_sqm_max ?? null],
    dealTypes: req.deal_types ?? null,
    excludePartial: req.exclude_partial,
    iqr: req.exclude_outlier ? req.outlier_iqr_multiplier : null,
  });
}
