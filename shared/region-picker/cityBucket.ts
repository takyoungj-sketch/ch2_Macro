/** 자치구로 나뉜 시 등: 시군구 5자리 → 의사 시 버킷 (예: 43114 → 43110). */
export function cityBucketFromSigungu(sigunguCode: string | null | undefined): string {
  const n = parseInt(String(sigunguCode ?? "").trim(), 10);
  if (Number.isNaN(n)) return "";
  return String(Math.floor(n / 10) * 10).padStart(5, "0");
}

export function extractCityFirstToken(sigunguName: string | null | undefined): string {
  const s = String(sigunguName ?? "").trim();
  if (!s) return "";
  const toks = s.split(/\s+/).filter(Boolean);
  if (toks.length < 2) return "";
  const head = toks[0]!;
  if (/(시|군)$/.test(head)) return head;
  return "";
}
