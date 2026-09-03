import { cityFullLabel } from "./cityDisplay";
import { formatRegionHierarchyLabel } from "./regionDisplay";
import { isSejongPseudoSigunguCode, isSejongRegionRow } from "./sejongRegion";
import type { RegionLevel, RegionNameInfo } from "./types";

/** Profile 검색창·칩에 표시할 한 줄 라벨 (D-030 P1-e). */
export function formatProfileSelectionQuery(
  level: RegionLevel,
  code: string,
  name: RegionNameInfo | null,
  sidoNameOf: (sidoCode: string) => string,
): string {
  if (level === "sido") return `${sidoNameOf(code)} 전체`;
  if (level === "city") return `${cityFullLabel(name, code)} 전체`.trim();
  if (!name) return code;
  if (level === "sigungu") {
    if (isSejongPseudoSigunguCode(code)) {
      return `${name.sido_name || "세종특별자치시"} 전체`.trim();
    }
    return `${name.sido_name} ${name.sigungu_name} 전체`.trim();
  }
  if (level === "beopjungri") {
    return formatRegionHierarchyLabel(name);
  }
  if (isSejongRegionRow(name)) {
    return `${name.sido_name} ${name.sigungu_name}`.trim();
  }
  return `${name.sido_name} ${name.sigungu_name} ${name.eupmyeondong_name}`.trim();
}
