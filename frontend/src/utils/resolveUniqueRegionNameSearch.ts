import type { RegionItem } from "../types";
import { cityBucketFromSigungu } from "./cityBucket";

function norm(s: string): string {
  return String(s ?? "").trim().toLowerCase().replace(/\s+/g, "");
}

export type UniqueRegionSearchPick =
  | { kind: "beopjungri"; row: RegionItem }
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

  // 시·도 단독: sido_name(예: '충청북도') 정확히 일치
  const sidoRows: RegionItem[] = [];
  for (const row of regions) {
    const n = norm(row.sido_name ?? "");
    if (n === qN) sidoRows.push(row);
  }
  const sidoCodes = new Set(
    sidoRows.map((r) => String(r.sido_code ?? "").trim()).filter(Boolean)
  );
  if (sidoCodes.size === 1) {
    const sidoCode = [...sidoCodes][0]!;
    return { kind: "sido_aggregate", sidoCode };
  }

  // 의사-시(예: '청주시'): sigungu_name 첫 토큰이 검색어와 일치 + 동일 시도 내에서 자치구 ≥2개
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
  const cityCandidates = [...cityBuckets.entries()].filter(
    ([, v]) => v.sigungus.size >= 2
  );
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
