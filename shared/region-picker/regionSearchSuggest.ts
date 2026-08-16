import { cityBucketFromSigungu, extractCityFirstToken } from "./cityBucket";
import { formatRegionHierarchyLabel } from "./regionDisplay";
import { isRetiredSidoCode } from "./retiredSido";
import {
  isSejongPseudoSigunguCode,
  isSejongRegionRow,
  sejongAdminNameMatchesQuery,
} from "./sejongRegion";
import type { RegionNameInfo } from "./types";

function norm(s: string): string {
  return String(s ?? "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "");
}

/** 검색어가 행정상 「읍·면」 단위 이름으로 보이면, 목록은 eup 한 줄씩만 두고 리·법정 줄은 펼치지 않는다. */
export function isEupMyeonUnitNameQuery(rawQuery: string): boolean {
  const qN = norm(rawQuery);
  if (qN.length < 2) return false;
  return qN.endsWith("읍") || qN.endsWith("면");
}

export type RegionSearchFlatEntry =
  | {
      kind: "sido_aggregate";
      sidoCode: string;
      primaryLabel: string;
      subtitle: string;
      countInSample: number;
      sample: RegionNameInfo;
    }
  | {
      kind: "city_aggregate";
      cityCode: string;
      cityName: string;
      sidoCode: string;
      sigunguCodes: string[];
      primaryLabel: string;
      subtitle: string;
      sample: RegionNameInfo;
    }
  | {
      kind: "sigungu_aggregate";
      sigunguCode: string;
      primaryLabel: string;
      subtitle: string;
      countInSample: number;
      sample: RegionNameInfo;
    }
  | {
      kind: "eup_aggregate";
      eupCode: string;
      primaryLabel: string;
      subtitle: string;
      countInSample: number;
      sample: RegionNameInfo;
    }
  | { kind: "beopjungri"; row: RegionNameInfo };

/**
 * 백엔드 검색 hit(법정단위별 행)을 동명 구분용 목록으로 변환합니다.
 * - 검색어가 …읍/…면 으로 끝나면: 전국 동명 읍·면을 행정 한 단위(eup) 카드로만 나열(하위 리·법정 줄 생략).
 * - 그 외: 법정동·리 이름·코드 또는 읍면 행정명 매칭으로 법정 줄을 만듭니다.
 * - 시도·자치구 묶음 시·시군구 상위 카드는 기존과 동일합니다.
 */
export function buildFlattenedRegionSuggestions(
  hits: RegionNameInfo[],
  rawQuery: string,
  opts?: { maxSigungu?: number; maxAgg?: number; maxBeop?: number },
): RegionSearchFlatEntry[] {
  const q = String(rawQuery ?? "").trim();
  const qN = norm(q);
  if (!qN || hits.length === 0) return [];

  const activeHits = hits.filter((h) => !isRetiredSidoCode(String(h.sido_code ?? "").trim()));
  if (activeHits.length === 0) return [];

  const maxSigungu = opts?.maxSigungu ?? 60;
  const maxAgg = opts?.maxAgg ?? 40;
  const maxBeop = opts?.maxBeop ?? 250;
  const eupMyeonFocused = isEupMyeonUnitNameQuery(rawQuery);

  const bySido = new Map<string, RegionNameInfo[]>();
  for (const h of activeHits) {
    const k = String(h.sido_code ?? "").trim();
    if (!k) continue;
    if (!bySido.has(k)) bySido.set(k, []);
    bySido.get(k)!.push(h);
  }
  const sidoAggregates: Extract<RegionSearchFlatEntry, { kind: "sido_aggregate" }>[] = [];
  for (const [sidoCode, bucket] of bySido.entries()) {
    if (isRetiredSidoCode(sidoCode)) continue;
    const sample = bucket[0]!;
    const sdcNn = norm(sidoCode);
    const sdnNn = norm(sample.sido_name ?? "");
    if (!(sdcNn === qN || sdnNn === qN || sdnNn.includes(qN))) continue;
    sidoAggregates.push({
      kind: "sido_aggregate",
      sidoCode,
      primaryLabel: String(sample.sido_name ?? "").trim(),
      subtitle: `시·도 전체 · 표본 ${bucket.length}건 (사전집계 단건 조회)`,
      countInSample: bucket.length,
      sample,
    });
  }
  sidoAggregates.sort((a, b) => a.primaryLabel.localeCompare(b.primaryLabel, "ko-KR"));

  const byCity = new Map<string, { sido: string; codes: Set<string>; sample: RegionNameInfo }>();
  for (const h of activeHits) {
    const city = extractCityFirstToken(h.sigungu_name);
    if (!city) continue;
    const sd = String(h.sido_code ?? "").trim();
    const sg = String(h.sigungu_code ?? "").trim();
    if (!sd || !sg) continue;
    const key = `${sd}::${city}`;
    if (!byCity.has(key)) byCity.set(key, { sido: sd, codes: new Set<string>(), sample: h });
    byCity.get(key)!.codes.add(sg);
  }
  const cityAggregates: Extract<RegionSearchFlatEntry, { kind: "city_aggregate" }>[] = [];
  for (const [key, info] of byCity.entries()) {
    if (info.codes.size < 2) continue;
    const city = key.split("::")[1] ?? "";
    const cityNn = norm(city);
    if (!(cityNn === qN || cityNn.includes(qN))) continue;
    const codes = [...info.codes].sort();
    const cityCode = codes.length ? cityBucketFromSigungu(codes[0]!) : "";
    const primaryLabel = [String(info.sample.sido_name ?? "").trim(), city].filter(Boolean).join(" ");
    cityAggregates.push({
      kind: "city_aggregate",
      cityCode,
      cityName: city,
      sidoCode: info.sido,
      sigunguCodes: codes,
      primaryLabel,
      subtitle: `시 전체 · 자치구 ${codes.length}개 묶음`,
      sample: info.sample,
    });
  }
  cityAggregates.sort((a, b) => a.primaryLabel.localeCompare(b.primaryLabel, "ko-KR"));

  const bySigungu = new Map<string, RegionNameInfo[]>();
  for (const h of activeHits) {
    const k = String(h.sigungu_code ?? "").trim();
    if (!k) continue;
    if (!bySigungu.has(k)) bySigungu.set(k, []);
    bySigungu.get(k)!.push(h);
  }

  const sigunguAggregates: Extract<RegionSearchFlatEntry, { kind: "sigungu_aggregate" }>[] = [];
  for (const [sigunguCode, bucket] of bySigungu.entries()) {
    if (isSejongPseudoSigunguCode(sigunguCode)) continue;
    const sample = bucket[0]!;
    const sgcNn = norm(sigunguCode);
    const matchesSigunguLevel = bucket.some((row) => {
      const chain = norm(`${row.sido_name ?? ""} ${row.sigungu_name ?? ""}`);
      const sgn = norm(row.sigungu_name ?? "");
      return sgcNn.includes(qN) || sgn.includes(qN) || chain.includes(qN);
    });
    if (!matchesSigunguLevel) continue;
    const primaryLabel = [sample.sido_name, sample.sigungu_name]
      .map((x) => String(x ?? "").trim())
      .filter(Boolean)
      .join(" ");
    sigunguAggregates.push({
      kind: "sigungu_aggregate",
      sigunguCode,
      primaryLabel,
      subtitle: `시군구 포함 · 검색 결과 표본 중 ${bucket.length}곳 확인됨`,
      countInSample: bucket.length,
      sample,
    });
  }
  sigunguAggregates.sort((a, b) => a.primaryLabel.localeCompare(b.primaryLabel, "ko-KR"));

  const eupAggregates: Extract<RegionSearchFlatEntry, { kind: "eup_aggregate" }>[] = [];

  if (eupMyeonFocused) {
    const byEup = new Map<string, RegionNameInfo[]>();
    for (const h of activeHits) {
      const k = String(h.eupmyeondong_code ?? "").trim();
      if (!k) continue;
      if (!byEup.has(k)) byEup.set(k, []);
      byEup.get(k)!.push(h);
    }

    for (const [eupCode, bucket] of byEup.entries()) {
      const sample = bucket[0]!;
      const eupNn = norm(sample.eupmyeondong_name ?? "");
      if (eupNn !== qN) continue;
      const prefix = [sample.sido_name, sample.sigungu_name, sample.eupmyeondong_name]
        .map((x) => String(x ?? "").trim())
        .filter(Boolean)
        .join(" ");
      eupAggregates.push({
        kind: "eup_aggregate",
        eupCode,
        primaryLabel: prefix,
        subtitle: `읍·면 행정 한 단위(8자 코드) · 하위 법정 ${bucket.length}곳`,
        countInSample: bucket.length,
        sample,
      });
    }
    eupAggregates.sort((a, b) => a.primaryLabel.localeCompare(b.primaryLabel, "ko-KR"));
  }

  const seenEupCodes = new Set(eupAggregates.map((e) => e.eupCode));
  const bySejongEup = new Map<string, RegionNameInfo[]>();
  for (const h of activeHits) {
    if (!isSejongRegionRow(h)) continue;
    if (!isSejongPseudoSigunguCode(String(h.sigungu_code ?? "").trim())) continue;
    if (
      !sejongAdminNameMatchesQuery(String(h.sigungu_name ?? ""), rawQuery, {
        allowContains: !eupMyeonFocused,
      })
    ) {
      continue;
    }
    const ec = String(h.eupmyeondong_code ?? "").trim();
    if (!ec || seenEupCodes.has(ec)) continue;
    if (!bySejongEup.has(ec)) bySejongEup.set(ec, []);
    bySejongEup.get(ec)!.push(h);
  }
  for (const [eupCode, bucket] of bySejongEup.entries()) {
    const sample = bucket[0]!;
    const adminLabel = String(sample.sigungu_name ?? "").trim();
    const primaryLabel = [sample.sido_name, adminLabel]
      .map((x) => String(x ?? "").trim())
      .filter(Boolean)
      .join(" ");
    eupAggregates.push({
      kind: "eup_aggregate",
      eupCode,
      primaryLabel,
      subtitle: `세종 행정동·읍·면 · 하위 법정 ${bucket.length}곳`,
      countInSample: bucket.length,
      sample,
    });
    seenEupCodes.add(eupCode);
  }
  eupAggregates.sort((a, b) => a.primaryLabel.localeCompare(b.primaryLabel, "ko-KR"));

  const beopMap = new Map<string, RegionNameInfo>();
  if (!eupMyeonFocused) {
    for (const h of activeHits) {
      const codeKey = String(h.beopjungri_code ?? "").trim();
      if (!codeKey) continue;
      const bn = norm(h.beopjungri_name ?? "");
      const bc = norm(codeKey);
      const eupNn = norm(h.eupmyeondong_name ?? "");
      const sejongAdminNn =
        isSejongRegionRow(h) && isSejongPseudoSigunguCode(String(h.sigungu_code ?? "").trim())
          ? norm(h.sigungu_name ?? "")
          : "";
      const matchesLeaf = bn.includes(qN) || bc.includes(qN);
      const matchesEupLabel = eupNn.includes(qN);
      const matchesSejongAdmin = sejongAdminNn.includes(qN);
      if (!(matchesLeaf || matchesEupLabel || matchesSejongAdmin)) continue;
      if (!beopMap.has(codeKey)) beopMap.set(codeKey, h);
    }
  }
  const beopRows = [...beopMap.values()].sort((a, b) =>
    formatRegionHierarchyLabel(a).localeCompare(formatRegionHierarchyLabel(b), "ko-KR"),
  );

  return [
    ...sidoAggregates,
    ...cityAggregates,
    ...sigunguAggregates.slice(0, maxSigungu),
    ...eupAggregates.slice(0, maxAgg),
    ...beopRows.slice(0, maxBeop).map((row) => ({ kind: "beopjungri" as const, row })),
  ];
}
