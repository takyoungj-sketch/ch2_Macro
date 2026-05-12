import type { RegionItem } from "../types";
import { formatRegionHierarchyLabel } from "./regionDisplay";

function norm(s: string): string {
  return String(s ?? "").trim().toLowerCase().replace(/\s+/g, "");
}

export type RegionSearchFlatEntry =
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
    ...sigunguAggregates.slice(0, maxSigungu),
    ...eupAggregates.slice(0, maxAgg),
    ...beopRows.slice(0, maxBeop).map((row) => ({ kind: "beopjungri" as const, row })),
  ];
}
