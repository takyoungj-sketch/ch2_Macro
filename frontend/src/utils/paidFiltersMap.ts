import { AREA_CATEGORIES, ROAD_CONDITIONS } from "../constants/paidFilters";
import type { PaidAnalysisRequest } from "../types";

/** 사용자가 '분석 제외'에 체크한 목록으로 실제 포함 집합 → API 필드 매핑 */
export function mergePaidExcludedIntoRequest(
  base: PaidAnalysisRequest,
  roadExcluded: readonly string[],
  areaExcluded: readonly string[]
): PaidAnalysisRequest {
  const inclRoads = ROAD_CONDITIONS.filter(
    (x) => !roadExcluded.some((e) => e === x)
  );
  const inclAreas = AREA_CATEGORIES.filter(
    (x) => !areaExcluded.some((e) => e === x)
  );

  return {
    ...base,
    road_conditions:
      inclRoads.length >= ROAD_CONDITIONS.length ? null : inclRoads.slice(),
    area_categories:
      inclAreas.length >= AREA_CATEGORIES.length ? null : inclAreas.slice(),
    land_categories: null,
    zone_types: null,
  };
}
