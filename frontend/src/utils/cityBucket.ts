/**
 * 자치구로 나뉜 시 등: 시군구 5자리를 "의사 시" 버킷으로 묶는다.
 * 예: 43114 → 43110 (청주), 44133 → 44130 (천안).
 */
export function cityBucketFromSigungu(sigunguCode: string | null | undefined): string {
  const n = parseInt(String(sigunguCode ?? "").trim(), 10);
  if (Number.isNaN(n)) return "";
  return String(Math.floor(n / 10) * 10).padStart(5, "0");
}
