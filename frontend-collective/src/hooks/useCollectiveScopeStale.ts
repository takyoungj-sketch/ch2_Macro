import { useRef } from "react";
import {
  isCollectiveRegionScopeHydration,
  isCollectiveRegionScopeStale,
  isCollectiveUserFilterStale,
  type CollectiveRegionScope,
  type CollectiveUserFilterFields,
} from "../utils/collectiveAnalysisUnits";

/**
 * 통계분석 스냅샷 vs 현재 필터.
 * 행정코드 resolve가 실행 직후 채워지는 것은 조건 변경으로 보지 않고,
 * scope를 다시 쓰지 않아 목록 재조회가 나지 않게 한다.
 */
export function useCollectiveScopeStale(
  scope: CollectiveUserFilterFields | null,
  live: CollectiveUserFilterFields,
  regionCodeScope: CollectiveRegionScope,
) {
  const baselineRef = useRef<CollectiveRegionScope>({});

  const filterStale = scope !== null && isCollectiveUserFilterStale(scope, live);

  if (scope === null) {
    baselineRef.current = {};
  } else if (
    !filterStale &&
    isCollectiveRegionScopeHydration(baselineRef.current, regionCodeScope)
  ) {
    baselineRef.current = regionCodeScope;
  }

  const scopeStale =
    scope !== null &&
    (filterStale || isCollectiveRegionScopeStale(baselineRef.current, regionCodeScope));

  return {
    filterStale,
    scopeStale,
    markRegionScopeCaptured: (snap: CollectiveRegionScope) => {
      baselineRef.current = snap;
    },
  };
}
