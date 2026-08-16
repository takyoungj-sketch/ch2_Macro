import { buildAppDeepLink, type RegionDeepLinkApp } from "@ch2/macro-shell/regionDeepLink";
import type { YearlyMixType } from "../types";

export type SourceApp = "land" | "built" | "collective" | "rent";

/**
 * 지역 프로필 → 개별 분석 앱 딥링크.
 * 각 앱이 `region_level` + `region_code` 를 읽어 지역을 미리 고른다.
 */
export function deepLinkTo(
  app: SourceApp,
  params: { regionLevel: string; regionCode: string },
): string {
  return buildAppDeepLink(app as RegionDeepLinkApp, params);
}

export const DOMINANT_TYPE_APP: Record<YearlyMixType, SourceApp> = {
  토지: "land",
  상가: "built",
  공장: "built",
  단독다가구: "built",
  아파트: "collective",
  오피스텔: "collective",
  연립다세대: "collective",
  분양권: "collective",
};

export const DOMINANT_TYPE_LABEL: Record<YearlyMixType, string> = {
  토지: "토지 상세분석",
  상가: "상업업무 상세분석",
  공장: "공장창고 상세분석",
  단독다가구: "단독다가구 상세분석",
  아파트: "아파트 상세분석",
  오피스텔: "오피스텔 상세분석",
  연립다세대: "연립다세대 상세분석",
  분양권: "분양권 상세분석",
};
