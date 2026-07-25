import type { YearlyMixType } from "../types";

export type SourceApp = "land" | "built" | "collective";

const APP_BASE: Record<SourceApp, string> = {
  land: "/land/",
  built: "/built/",
  collective: "/collective/",
};

/**
 * 지역 프로필 → 개별 분석 앱 딥링크.
 * NOTE: land/built/collective 앱은 아직 region_level/region_code 쿼리파라미터를 읽어
 * 자동 선택하지 않는다(Phase 5 진행 중 — entry-points). 현재는 앱 기본 화면으로 이동하며,
 * 파라미터는 향후 각 앱이 소비할 수 있도록 미리 붙여둔다(하위호환, 무해).
 */
export function deepLinkTo(
  app: SourceApp,
  params: { regionLevel: string; regionCode: string },
): string {
  const qs = new URLSearchParams({
    region_level: params.regionLevel,
    region_code: params.regionCode,
  });
  return `${APP_BASE[app]}?${qs.toString()}`;
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
