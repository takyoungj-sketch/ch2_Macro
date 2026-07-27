import {
  resolveBeopjungriFromLooseAddressLine,
  tokenizeLooseAddressLine,
  type RegionNameInfo,
} from "@ch2/region-picker";

/** 토큰별 API 검색 hit를 beopjungri_code 기준으로 교집합. */
export function intersectRegionRowsByBeop(hitsPerToken: RegionNameInfo[][]): RegionNameInfo[] {
  if (hitsPerToken.length === 0) return [];
  const codeMaps = hitsPerToken.map(
    (hits) => new Map(hits.map((r) => [String(r.beopjungri_code ?? "").trim(), r])),
  );
  let codes = new Set(codeMaps[0]!.keys());
  for (let i = 1; i < codeMaps.length; i++) {
    const next = new Set(codeMaps[i]!.keys());
    codes = new Set([...codes].filter((c) => next.has(c)));
  }
  return [...codes]
    .sort((a, b) => a.localeCompare(b, "ko-KR"))
    .map((c) => codeMaps[0]!.get(c) ?? codeMaps.find((m) => m.has(c))!.get(c)!)
    .filter(Boolean);
}

/**
 * 전국 카탈로그가 아직 없거나 일부만 로드됐을 때 loose 주소를 토큰별 검색으로 좁힌다.
 */
export async function resolveLooseAddressViaTokenSearch(
  fetchTokenHits: (token: string) => Promise<RegionNameInfo[]>,
  raw: string,
): Promise<{ rows: RegionNameInfo[]; codes: string[] }> {
  const tokens = tokenizeLooseAddressLine(raw);
  if (tokens.length === 0) return { rows: [], codes: [] };
  if (tokens.length === 1 && /^\d{10}$/.test(tokens[0]!)) {
    const hits = await fetchTokenHits(tokens[0]!);
    return resolveBeopjungriFromLooseAddressLine(hits, raw);
  }
  const hitsPerToken = await Promise.all(tokens.map((t) => fetchTokenHits(t)));
  const intersected = intersectRegionRowsByBeop(hitsPerToken);
  return resolveBeopjungriFromLooseAddressLine(intersected, raw);
}
