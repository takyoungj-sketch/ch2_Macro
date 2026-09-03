import { formatRegionHierarchyLabel } from "./regionDisplay";
import type { RegionSearchFlatEntry } from "./regionSearchSuggest";
import type { RegionLevel, RegionNameInfo, RegionSearchResult } from "./types";

/**
 * 리가 없는 법정동: 10자리 코드가 `…00` 이거나, 동 이름과 리 이름이 같다.
 * 지적 잎(원장 키)은 10자리로 남기고, 프로필 행정 체급에서는 읍면동과 동일하다.
 */
export function isLegalDongWithoutRi(
  code: string,
  names?: Pick<RegionNameInfo, "eupmyeondong_name" | "beopjungri_name"> | null,
): boolean {
  const c = String(code ?? "").trim();
  if (/^\d{10}$/.test(c) && c.endsWith("00")) return true;
  if (!names) return false;
  const eup = String(names.eupmyeondong_name ?? "").trim();
  const beop = String(names.beopjungri_name ?? "").trim();
  return Boolean(eup && beop && eup === beop && /^\d{10}$/.test(c));
}

/**
 * 프로필 진입 grain. 리가 없는 동은 읍면동으로 올린다.
 * `coercedFromBeop`은 그 읍면동 프로필이 없을 때(전국 3곳) 되돌릴 원래 10자리.
 */
export function coerceProfileRegionSelection(sel: {
  regionLevel: RegionLevel;
  regionCode: string;
}): { regionLevel: RegionLevel; regionCode: string; coercedFromBeop?: string } {
  const code = String(sel.regionCode ?? "").trim();
  if (sel.regionLevel === "beopjungri" && isLegalDongWithoutRi(code)) {
    return { regionLevel: "eupmyeondong", regionCode: code.slice(0, 8), coercedFromBeop: code };
  }
  return { regionLevel: sel.regionLevel, regionCode: code };
}

/**
 * 프로필 검색 확정: 리가 없는 동은 읍면동(8자리)으로 연다. 토지 picker는 호출하지 않음.
 * 이미 읍면동으로 올라온 제안도 원래 10자리를 `originBeopCode`로 달아 되돌릴 수 있게 한다.
 */
export function coerceProfileSearchResult(
  result: RegionSearchResult,
  row?: RegionNameInfo | null,
): RegionSearchResult {
  const rowBeop = String(row?.beopjungri_code ?? "").trim();
  const rowEup = String(row?.eupmyeondong_code ?? "").trim();

  if (result.level === "eupmyeondong") {
    if (row && rowEup === String(result.code ?? "").trim() && isLegalDongWithoutRi(rowBeop, row)) {
      return { ...result, originBeopCode: rowBeop };
    }
    return result;
  }

  if (result.level !== "beopjungri") return result;
  const code = String(result.code ?? "").trim();
  if (!isLegalDongWithoutRi(code, row ?? undefined)) return result;
  const eup = rowEup || (code.length === 10 ? code.slice(0, 8) : "");
  if (!/^\d{8}$/.test(eup)) return result;
  return {
    level: "eupmyeondong",
    code: eup,
    label: row ? formatRegionHierarchyLabel(row) : result.label,
    sublabel: "읍·면·동",
    originBeopCode: code,
  };
}

/** 프로필 제안: 리가 없는 동을 「리」 줄로 두지 않고 읍면동 한 줄로 올린다. */
export function remapDongOnlyBeopSuggestions(
  entries: RegionSearchFlatEntry[],
): RegionSearchFlatEntry[] {
  const seenEup = new Set(
    entries
      .filter((e): e is Extract<RegionSearchFlatEntry, { kind: "eup_aggregate" }> => e.kind === "eup_aggregate")
      .map((e) => e.eupCode),
  );
  const out: RegionSearchFlatEntry[] = [];
  for (const e of entries) {
    if (e.kind !== "beopjungri") {
      out.push(e);
      continue;
    }
    if (!isLegalDongWithoutRi(String(e.row.beopjungri_code ?? "").trim(), e.row)) {
      out.push(e);
      continue;
    }
    const eup = String(e.row.eupmyeondong_code ?? "").trim();
    if (!eup || seenEup.has(eup)) continue;
    seenEup.add(eup);
    const primaryLabel = [e.row.sido_name, e.row.sigungu_name, e.row.eupmyeondong_name]
      .map((x) => String(x ?? "").trim())
      .filter(Boolean)
      .join(" ");
    out.push({
      kind: "eup_aggregate",
      eupCode: eup,
      primaryLabel,
      subtitle: "읍·면·동",
      countInSample: 1,
      sample: e.row,
    });
  }
  return out;
}
