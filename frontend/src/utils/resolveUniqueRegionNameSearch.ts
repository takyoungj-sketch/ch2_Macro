import type { RegionItem } from "../types";

function norm(s: string): string {
  return String(s ?? "").trim().toLowerCase().replace(/\s+/g, "");
}

export type UniqueRegionSearchPick =
  | { kind: "beopjungri"; row: RegionItem }
  | { kind: "eup_aggregate"; eupCode: string }
  | { kind: "sigungu_aggregate"; sigunguCode: string };

/**
 * 검색어가 전국에서 한 시군구·읍면동·법정단위로만 안내될 때 자동 선택에 쓰입니다.
 * - 법정동·리: 정규화 후 완전 일치이거나, 검색어 3글자 이상일 때 이름에 부분 일치(포함)하면 묶음
 * - 읍·면·동·시·군·구: 완전 일치만 (짧은 글자로 잘못 합치는 것 방지)
 */
export function tryResolveUniqueRegionSearch(
  regions: readonly RegionItem[],
  rawQuery: string,
  viewMode: "free" | "paid"
): UniqueRegionSearchPick | null {
  const qN = norm(String(rawQuery ?? "").trim());
  if (qN.length < 2) return null;

  const beopRows: RegionItem[] = [];
  for (const row of regions) {
    const n = norm(row.beopjungri_name ?? "");
    const exact = n === qN;
    const sub = qN.length >= 3 && n.includes(qN);
    if (exact || sub) beopRows.push(row);
  }
  const beopCodes = new Set(
    beopRows.map((r) => String(r.beopjungri_code ?? "").trim()).filter(Boolean)
  );
  if (beopCodes.size === 1) {
    const code = [...beopCodes][0]!;
    const row = beopRows.find((r) => String(r.beopjungri_code ?? "").trim() === code)!;
    return { kind: "beopjungri", row };
  }

  if (viewMode !== "paid") return null;

  const eupRows: RegionItem[] = [];
  for (const row of regions) {
    const n = norm(row.eupmyeondong_name ?? "");
    if (n === qN) eupRows.push(row);
  }
  const eupCodes = new Set(
    eupRows.map((r) => String(r.eupmyeondong_code ?? "").trim()).filter(Boolean)
  );
  if (eupCodes.size === 1) {
    const eupCode = [...eupCodes][0]!;
    return { kind: "eup_aggregate", eupCode };
  }

  const sigRows: RegionItem[] = [];
  for (const row of regions) {
    const n = norm(row.sigungu_name ?? "");
    if (n === qN) sigRows.push(row);
  }
  const sigCodes = new Set(
    sigRows.map((r) => String(r.sigungu_code ?? "").trim()).filter(Boolean)
  );
  if (sigCodes.size === 1) {
    const sigunguCode = [...sigCodes][0]!;
    return { kind: "sigungu_aggregate", sigunguCode };
  }

  return null;
}
