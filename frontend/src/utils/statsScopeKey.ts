export function normalizeBeopjungriCodeList(codes: readonly string[]): string[] {
  return [...new Set(codes.map((c) => String(c ?? "").trim()).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b, "ko-KR")
  );
}

/** 기본 통계 조회 확정 스코프 — 법정리 코드 집합을 정규화한 문자열 (순서 무관 비교용) */
export function statsScopeKeyFromBeopjungriCodes(codes: readonly string[]): string {
  return normalizeBeopjungriCodeList(codes).join("|");
}
