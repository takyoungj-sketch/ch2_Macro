import type { RegionItem } from "../types";
import { formatRegionHierarchyLabel } from "./regionDisplay";

function norm(s: string): string {
  return String(s ?? "").trim().toLowerCase().replace(/\s+/g, "");
}

export type RegionSearchFlatEntry =
  | {
      kind: "sido_aggregate";
      sidoCode: string;
      primaryLabel: string;
      subtitle: string;
      countInSample: number;
      sample: RegionItem;
    }
  | {
      /** 청주시·고양시 같이 region_codes 에 별도 코드가 없는 의사-시. 자치구 sigungu_code 묶음으로 표시. */
      kind: "city_aggregate";
      cityName: string;
      sidoCode: string;
      sigunguCodes: string[];
      primaryLabel: string;
      subtitle: string;
      sample: RegionItem;
    }
  | {
      kind: "sigungu_aggregate";
      sigunguCode: string;
      primaryLabel: string;
      subtitle: string;
      countInSample: number;
      sample: RegionItem;
    }
  | {
      kind: "eup_aggregate";
      eupCode: string;
      primaryLabel: string;
      subtitle: string;
      countInSample: number;
      sample: RegionItem;
    }
  | { kind: "beopjungri"; row: RegionItem };

/**
 * 백엔드 검색 hit(법정단위별 행)을 동명 구분용 목록으로 변환합니다.
 * - 검색어가 시군구명·코드와 맞으면 "[시군구 포함]" 묶음(클릭 시 그 시군구 전체 법정단위 병합).
 * - 검색어가 읍·면·동 이름과 맞으면 해당 단위별 "[읍면동 포함]" 묶음.
 * - 법정리·법정동 이름(또는 코드) 일치 행은 풀 경로 레이블로 나열합니다.
 */
/** "청주시 상당구" → "청주시" / "수원시 영통구" → "수원시" / "포항시 남구" → "포항시" 등.
 *  region_codes 에 별도 코드가 없는 의사-시(시 단위) 첫 토큰을 추출. */
function extractCityFirstToken(sigunguName: string | null | undefined): string {
  const s = String(sigunguName ?? "").trim();
  if (!s) return "";
  const toks = s.split(/\s+/).filter(Boolean);
  if (toks.length < 2) return "";
  const head = toks[0]!;
  if (/(시|군)$/.test(head)) return head;
  return "";
}

export function buildFlattenedRegionSuggestions(
  hits: RegionItem[],
  rawQuery: string,
  opts?: { maxSigungu?: number; maxAgg?: number; maxBeop?: number }
): RegionSearchFlatEntry[] {
  const q = String(rawQuery ?? "").trim();
  const qN = norm(q);
  if (!qN || hits.length === 0) return [];

  const maxSigungu = opts?.maxSigungu ?? 60;
  const maxAgg = opts?.maxAgg ?? 40;
  const maxBeop = opts?.maxBeop ?? 250;

  // 시·도 묶음: hits 안에 검색어가 sido_name 이나 sido_code 와 맞는 행이 있으면 시도 한 줄.
  const bySido = new Map<string, RegionItem[]>();
  for (const h of hits) {
    const k = String(h.sido_code ?? "").trim();
    if (!k) continue;
    if (!bySido.has(k)) bySido.set(k, []);
    bySido.get(k)!.push(h);
  }
  const sidoAggregates: Extract<RegionSearchFlatEntry, { kind: "sido_aggregate" }>[] = [];
  for (const [sidoCode, bucket] of bySido.entries()) {
    const sample = bucket[0];
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
  sidoAggregates.sort((a, b) =>
    a.primaryLabel.localeCompare(b.primaryLabel, "ko-KR")
  );

  // 의사-시(City) 묶음: sigungu_name 첫 토큰(예: "청주시")이 검색어와 같으면 그 시도의 자치구들을 묶는다.
  const byCity = new Map<string, { sido: string; codes: Set<string>; sample: RegionItem }>();
  for (const h of hits) {
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
    const primaryLabel = [String(info.sample.sido_name ?? "").trim(), city]
      .filter(Boolean)
      .join(" ");
    cityAggregates.push({
      kind: "city_aggregate",
      cityName: city,
      sidoCode: info.sido,
      sigunguCodes: codes,
      primaryLabel,
      subtitle: `시 전체 · 자치구 ${codes.length}개 묶음`,
      sample: info.sample,
    });
  }
  cityAggregates.sort((a, b) =>
    a.primaryLabel.localeCompare(b.primaryLabel, "ko-KR")
  );

  const bySigungu = new Map<string, RegionItem[]>();
  for (const h of hits) {
    const k = String(h.sigungu_code ?? "").trim();
    if (!k) continue;
    if (!bySigungu.has(k)) bySigungu.set(k, []);
    bySigungu.get(k)!.push(h);
  }

  const sigunguAggregates: Extract<
    RegionSearchFlatEntry,
    { kind: "sigungu_aggregate" }
  >[] = [];

  for (const [sigunguCode, bucket] of bySigungu.entries()) {
    const sample = bucket[0];
    const sgcNn = norm(sigunguCode);
    const matchesSigunguLevel = bucket.some((row) => {
      const chain = norm(`${row.sido_name ?? ""} ${row.sigungu_name ?? ""}`);
      const sgn = norm(row.sigungu_name ?? "");
      return (
        sgcNn.includes(qN) || sgn.includes(qN) || chain.includes(qN)
      );
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

  sigunguAggregates.sort((a, b) =>
    a.primaryLabel.localeCompare(b.primaryLabel, "ko-KR")
  );

  const byEup = new Map<string, RegionItem[]>();
  for (const h of hits) {
    const k = String(h.eupmyeondong_code ?? "").trim();
    if (!k) continue;
    if (!byEup.has(k)) byEup.set(k, []);
    byEup.get(k)!.push(h);
  }

  const eupAggregates: Extract<RegionSearchFlatEntry, { kind: "eup_aggregate" }>[] =
    [];

  for (const [eupCode, bucket] of byEup.entries()) {
    const sample = bucket[0];
    const eupNn = norm(sample.eupmyeondong_name ?? "");
    if (!eupNn.includes(qN)) continue;
    const prefix = [sample.sido_name, sample.sigungu_name, sample.eupmyeondong_name]
      .map((x) => String(x ?? "").trim())
      .filter(Boolean)
      .join(" ");
    eupAggregates.push({
      kind: "eup_aggregate",
      eupCode,
      primaryLabel: prefix,
      subtitle: `법정단위 포함 · 검색 결과 중 ${bucket.length}곳 확인됨`,
      countInSample: bucket.length,
      sample,
    });
  }

  eupAggregates.sort((a, b) =>
    a.primaryLabel.localeCompare(b.primaryLabel, "ko-KR")
  );

  const beopMap = new Map<string, RegionItem>();
  for (const h of hits) {
    const codeKey = String(h.beopjungri_code ?? "").trim();
    if (!codeKey) continue;
    const bn = norm(h.beopjungri_name ?? "");
    const bc = norm(codeKey);
    if (!(bn.includes(qN) || bc.includes(qN))) continue;
    if (!beopMap.has(codeKey)) beopMap.set(codeKey, h);
  }
  const beopRows = [...beopMap.values()].sort((a, b) =>
    formatRegionHierarchyLabel(a).localeCompare(formatRegionHierarchyLabel(b), "ko-KR")
  );

  return [
    ...sidoAggregates,
    ...cityAggregates,
    ...sigunguAggregates.slice(0, maxSigungu),
    ...eupAggregates.slice(0, maxAgg),
    ...beopRows.slice(0, maxBeop).map((row) => ({ kind: "beopjungri" as const, row })),
  ];
}
