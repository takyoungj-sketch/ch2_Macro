import { useEffect, useMemo, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { parseRegionDeepLink } from "@ch2/macro-shell/regionDeepLink";
import { fetchRegions } from "../api/client";
import { REGIONS_CATALOG_QUERY_KEY } from "../constants/regionsCatalog";
import { useAppStore } from "../store";
import { resolveUnionBeopjungriCodes } from "../utils/regionTier";
import { statsScopeKeyFromBeopjungriCodes } from "../utils/statsScopeKey";

/** 프로필 딥링크 `?region_level=&region_code=` → 토지 지역 선택·기본통계 */
export function useLandDeepLink() {
  const link = useMemo(() => parseRegionDeepLink(), []);
  const applied = useRef(false);
  const committed = useRef(false);
  const applyDeepLinkRegion = useAppStore((s) => s.applyDeepLinkRegion);
  const commitStatsDisplayScope = useAppStore((s) => s.commitStatsDisplayScope);
  const kickPaidBasicStatsAnalysis = useAppStore((s) => s.kickPaidBasicStatsAnalysis);
  const tierSelection = useAppStore((s) => s.tierSelection);

  useEffect(() => {
    if (!link || applied.current) return;
    applied.current = true;
    applyDeepLinkRegion(link.regionLevel, link.regionCode);
    if (link.regionLevel === "beopjungri") {
      commitStatsDisplayScope(link.regionCode);
      committed.current = true;
    }
  }, [link, applyDeepLinkRegion, commitStatsDisplayScope]);

  const { data: regions = [] } = useQuery({
    queryKey: REGIONS_CATALOG_QUERY_KEY,
    queryFn: () => fetchRegions(),
    staleTime: 6 * 60 * 60 * 1000,
    enabled: Boolean(link && link.regionLevel !== "beopjungri"),
  });

  useEffect(() => {
    if (!link || committed.current || link.regionLevel === "beopjungri") return;
    if (regions.length === 0) return;
    const codes = resolveUnionBeopjungriCodes(regions, tierSelection);
    if (codes.length === 0) return;
    kickPaidBasicStatsAnalysis();
    commitStatsDisplayScope(statsScopeKeyFromBeopjungriCodes(codes));
    committed.current = true;
  }, [link, regions, tierSelection, kickPaidBasicStatsAnalysis, commitStatsDisplayScope]);
}
