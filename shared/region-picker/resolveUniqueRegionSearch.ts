import { cityBucketFromSigungu } from "./cityBucket";
import { isEupMyeonUnitNameQuery } from "./regionSearchSuggest";
import {
  isSejongPseudoSigunguCode,
  uniqueSejongEupCodeForAdminName,
} from "./sejongRegion";
import type { RegionNameInfo } from "./types";

export type RegionPickerViewMode = "free" | "paid";

function norm(s: string): string {
  return String(s ?? "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "");
}

export type UniqueRegionSearchPick =
  | { kind: "beopjungri"; row: RegionNameInfo }
  | { kind: "eup_aggregate"; eupCode: string }
  | { kind: "sigungu_aggregate"; sigunguCode: string }
  | { kind: "sido_aggregate"; sidoCode: string }
  | {
      kind: "city_aggregate";
      cityCode: string;
      cityName: string;
      sidoCode: string;
      sigunguCodes: string[];
    };

/**
 * 검색어가 전국 카탈로그 기준 단일 후보로 확정 가능할 때 Enter 자동 선택에 사용.
 * - …읍/…면 검색이면 행정명 전국 유일 eup → eup_aggregate.(그 외는 목록에서 고름.)
 * - 법정: 이름 포함·코드 일치 등(읍면 전용 검색일 땐 읍명 일치만으로 법정 후보 묶지 않음)
 */
export function tryResolveUniqueRegionSearch(
  regions: readonly RegionNameInfo[],
  rawQuery: string,
  viewMode: RegionPickerViewMode,
): UniqueRegionSearchPick | null {
  const qN = norm(String(rawQuery ?? "").trim());
  if (qN.length < 2) return null;

  const eupMyeonQ = isEupMyeonUnitNameQuery(rawQuery);

  const beopRows: RegionNameInfo[] = [];
  for (const row of regions) {
    const n = norm(row.beopjungri_name ?? "");
    const exact = n === qN;
    const sub = qN.length >= 3 && n.includes(qN);
    const codeEq = norm(String(row.beopjungri_code ?? "").trim()) === qN;
    const eupEx = !eupMyeonQ && norm(row.eupmyeondong_name ?? "") === qN;
    if (exact || sub || eupEx || codeEq) beopRows.push(row);
  }
  const beopCodes = new Set(
    beopRows.map((r) => String(r.beopjungri_code ?? "").trim()).filter(Boolean),
  );
  if (beopCodes.size === 1) {
    const code = [...beopCodes][0]!;
    const row = beopRows.find((r) => String(r.beopjungri_code ?? "").trim() === code)!;
    return { kind: "beopjungri", row };
  }

  if (viewMode !== "paid") return null;

  if (eupMyeonQ) {
    const eupCodes = new Set<string>();
    for (const row of regions) {
      const en = norm(row.eupmyeondong_name ?? "");
      if (en !== qN) continue;
      const ec = String(row.eupmyeondong_code ?? "").trim();
      if (ec) eupCodes.add(ec);
    }
    if (eupCodes.size === 1) {
      return { kind: "eup_aggregate", eupCode: [...eupCodes][0]! };
    }
    const sejongEup = uniqueSejongEupCodeForAdminName(regions, qN);
    if (sejongEup) {
      return { kind: "eup_aggregate", eupCode: sejongEup };
    }
  }

  const sigRows: RegionNameInfo[] = [];
  for (const row of regions) {
    const n = norm(row.sigungu_name ?? "");
    if (n === qN) sigRows.push(row);
  }
  const sigCodes = new Set(
    sigRows.map((r) => String(r.sigungu_code ?? "").trim()).filter(Boolean),
  );
  if (sigCodes.size === 1) {
    const sigunguCode = [...sigCodes][0]!;
    if (isSejongPseudoSigunguCode(sigunguCode)) {
      const sejongEup = uniqueSejongEupCodeForAdminName(regions, qN);
      if (sejongEup) {
        return { kind: "eup_aggregate", eupCode: sejongEup };
      }
    }
    return { kind: "sigungu_aggregate", sigunguCode };
  }

  const sidoRows: RegionNameInfo[] = [];
  for (const row of regions) {
    const n = norm(row.sido_name ?? "");
    if (n === qN) sidoRows.push(row);
  }
  const sidoCodes = new Set(
    sidoRows.map((r) => String(r.sido_code ?? "").trim()).filter(Boolean),
  );
  if (sidoCodes.size === 1) {
    const sidoCode = [...sidoCodes][0]!;
    return { kind: "sido_aggregate", sidoCode };
  }

  const cityBuckets = new Map<string, { sido: string; sigungus: Set<string> }>();
  for (const row of regions) {
    const sgName = String(row.sigungu_name ?? "").trim();
    if (!sgName) continue;
    const toks = sgName.split(/\s+/).filter(Boolean);
    if (toks.length < 2) continue;
    const head = toks[0]!;
    if (!/(시|군)$/.test(head)) continue;
    if (norm(head) !== qN) continue;
    const sd = String(row.sido_code ?? "").trim();
    const sg = String(row.sigungu_code ?? "").trim();
    if (!sd || !sg) continue;
    const key = `${sd}::${head}`;
    if (!cityBuckets.has(key)) cityBuckets.set(key, { sido: sd, sigungus: new Set<string>() });
    cityBuckets.get(key)!.sigungus.add(sg);
  }
  const cityCandidates = [...cityBuckets.entries()].filter(([, v]) => v.sigungus.size >= 2);
  if (cityCandidates.length === 1) {
    const [key, v] = cityCandidates[0]!;
    const cityName = key.split("::")[1] ?? "";
    const sigunguCodes = [...v.sigungus].sort();
    const cityCode = sigunguCodes.length ? cityBucketFromSigungu(sigunguCodes[0]!) : "";
    return {
      kind: "city_aggregate",
      cityCode,
      cityName,
      sidoCode: v.sido,
      sigunguCodes,
    };
  }

  return null;
}
