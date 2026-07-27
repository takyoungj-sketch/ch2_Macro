import { formatRegionHierarchyLabel } from "./regionDisplay";
import type { RegionSearchFlatEntry } from "./regionSearchSuggest";
import type { UniqueRegionSearchPick } from "./resolveUniqueRegionSearch";
import type { RegionSearchResult } from "./types";

export function flatEntryToSearchResult(entry: RegionSearchFlatEntry): RegionSearchResult {
  switch (entry.kind) {
    case "sido_aggregate":
      return {
        level: "sido",
        code: entry.sidoCode,
        label: entry.primaryLabel,
        sublabel: entry.subtitle,
      };
    case "city_aggregate":
      return {
        level: "city",
        code: entry.cityCode,
        label: entry.primaryLabel,
        sublabel: entry.subtitle,
      };
    case "sigungu_aggregate":
      return {
        level: "sigungu",
        code: entry.sigunguCode,
        label: entry.primaryLabel,
        sublabel: entry.subtitle,
      };
    case "eup_aggregate":
      return {
        level: "eupmyeondong",
        code: entry.eupCode,
        label: entry.primaryLabel,
        sublabel: entry.subtitle,
      };
    case "beopjungri":
      return {
        level: "beopjungri",
        code: String(entry.row.beopjungri_code).trim(),
        label: formatRegionHierarchyLabel(entry.row),
        sublabel: String(entry.row.beopjungri_code).trim(),
      };
  }
}

export function uniquePickToSearchResult(pick: UniqueRegionSearchPick): RegionSearchResult {
  switch (pick.kind) {
    case "beopjungri":
      return flatEntryToSearchResult({ kind: "beopjungri", row: pick.row });
    case "eup_aggregate":
      return {
        level: "eupmyeondong",
        code: pick.eupCode,
        label: pick.eupCode,
        sublabel: "읍·면·동",
      };
    case "sigungu_aggregate":
      return {
        level: "sigungu",
        code: pick.sigunguCode,
        label: pick.sigunguCode,
        sublabel: "시군구",
      };
    case "sido_aggregate":
      return {
        level: "sido",
        code: pick.sidoCode,
        label: pick.sidoCode,
        sublabel: "시/도",
      };
    case "city_aggregate":
      return {
        level: "city",
        code: pick.cityCode,
        label: pick.cityName,
        sublabel: "시",
      };
  }
}
